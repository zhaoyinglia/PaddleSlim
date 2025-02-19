# Copyright (c) 2022 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import numpy as np
import argparse
import paddle
from paddleslim.common import load_config, load_onnx_model
from paddleslim.quant import quant_post_static
from paddleslim.quant import quant_recon_static
from dataset import COCOTrainDataset


def argsparser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--config_path',
        type=str,
        default=None,
        help="path of post training quantization config.",
        required=True)
    parser.add_argument(
        '--save_dir',
        type=str,
        default='ptq_out',
        help="directory to save compressed model.")
    parser.add_argument(
        '--devices',
        type=str,
        default='gpu',
        help="which device used to compress.")
    parser.add_argument(
        '--algo', type=str, default='avg', help="post quant algo.")
    parser.add_argument(
        '--round_type', type=str, default='adaround', help="round type.")
    parser.add_argument('--gpu', type=int, default=0, help='gpu index')

    parser.add_argument(
        '--recon_level',
        type=str,
        default='layer-wise',
        help='reconstruction level')
    parser.add_argument(
        '--simulate_activation_quant',
        type=bool,
        default=False,
        help='simulate activation quant')
    parser.add_argument(
        '--epochs', type=int, default=20, help='steps to reconstruct')

    return parser


def main():
    global config
    config = load_config(FLAGS.config_path)

    input_name = 'x2paddle_image_arrays' if config[
        'arch'] == 'YOLOv6' else 'x2paddle_images'
    dataset = COCOTrainDataset(
        dataset_dir=config['dataset_dir'],
        image_dir=config['val_image_dir'],
        anno_path=config['val_anno_path'],
        input_name=input_name)
    train_loader = paddle.io.DataLoader(
        dataset, batch_size=1, shuffle=True, drop_last=True, num_workers=0)

    place = paddle.CUDAPlace(
        FLAGS.gpu) if FLAGS.devices == 'gpu' else paddle.CPUPlace()
    exe = paddle.static.Executor(place)

    # since the type pf model converted from pytorch is onnx,
    # use load_onnx_model firstly and rename the model_dir
    load_onnx_model(config["model_dir"])
    inference_model_path = config["model_dir"].rstrip().rstrip(
        '.onnx') + '_infer'

    quant_recon_static(
        executor=exe,
        model_dir=inference_model_path,
        quantize_model_path=FLAGS.save_dir,
        data_loader=train_loader,
        model_filename='model.pdmodel',
        params_filename='model.pdiparams',
        batch_size=32,
        batch_nums=10,
        algo=FLAGS.algo,
        hist_percent=0.999,
        is_full_quantize=False,
        bias_correction=False,
        onnx_format=False,
        weight_quantize_type='channel_wise_abs_max',
        recon_level=FLAGS.recon_level,
        simulate_activation_quant=FLAGS.simulate_activation_quant,
        regions=config['regions'],
        region_weights_names=config['region_weights_names'],
        epochs=FLAGS.epochs,
        lr=0.1)


if __name__ == '__main__':
    paddle.enable_static()
    parser = argsparser()
    FLAGS = parser.parse_args()

    assert FLAGS.devices in ['cpu', 'gpu', 'xpu', 'npu']
    paddle.set_device(FLAGS.devices)

    main()
