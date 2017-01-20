#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import os
import tensorflow as tf
import tensorflow.contrib.slim as slim
from tensorflow.contrib.slim.nets import resnet_v1
from tensorflow.contrib.slim.nets import resnet_utils

def tiny (X, num_classes=2):
    # stride is  2 * 2 * 2 * 2 = 16
    net = X
    layers = [X]
    with tf.name_scope('simple'):
        # slim.arg_scope([slim.conv2d]):
        # slim.conv2d defaults:
        #   padding = 'SAME'
        #   activation_fn = nn.relu
        # parameters: net, out_channels, kernel_size, stride
        net = slim.conv2d(net, 64, 3, 2, scope='conv1')
        net = slim.max_pool2d(net, 2, 2, scope='pool1')
        net = slim.conv2d(net, 128, 3, 1, scope='conv2_1')
        net = slim.conv2d(net, 128, 3, 1, scope='conv2_2')
        net = slim.max_pool2d(net, 2, 2, scope='pool2')
        net = slim.conv2d(net, 256, 3, 1, scope='conv3_1')
        net = slim.conv2d(net, 256, 3, 1, scope='conv3_2')
        net = slim.conv2d(net, 128, 1, 1, scope='conv5')
        #net = slim.dropout(net, keep_prob=0.9, scope='dropout')
        net = slim.conv2d(net, 32, 1, 1, scope='conv6',
                            activation_fn=None,
                            normalizer_fn=None,
                         )
        net = slim.conv2d_transpose(net, num_classes, 17, 8, scope='upscale')
    net = tf.identity(net, 'logits')
    return net, 16


# conv2d and conv2d_transpose

# conv2d output size if padding = 'SAME':   W <- (W + S -1)/S 
#                                 'VALID':  W <- (W - F + S)/S
def simple (X, num_classes=2):
    # stride is  2 * 2 * 2 * 2 = 16
    net = X
    layers = [X]
    with tf.name_scope('simple'):
        # slim.arg_scope([slim.conv2d]):
        # slim.conv2d defaults:
        #   padding = 'SAME'
        #   activation_fn = nn.relu
        # parameters: net, out_channels, kernel_size, stride
        net = slim.conv2d(net, 100, 5, 2, scope='conv1')
        net = slim.max_pool2d(net, 2, 2, scope='pool1')
        net = slim.conv2d(net, 200, 5, 2, scope='conv2')
        net = slim.max_pool2d(net, 2, 2, scope='pool2')
        net = slim.conv2d(net, 300, 3, 1, scope='conv3')
        net = slim.conv2d(net, 300, 3, 1, scope='conv4')
        net = slim.dropout(net, keep_prob=0.9, scope='dropout')
        net = slim.conv2d(net, 20, 1, 1, scope='layer5')
        net = slim.conv2d_transpose(net, num_classes, 31, 16, scope='upscale')
    net = tf.identity(net, 'logits')
    return net, 16

def  resnet_v1_50 (X, num_classes=2):
    with tf.name_scope('resnet_v1_50'):
        net, _ = resnet_v1.resnet_v1_50(X,
                                num_classes=num_classes,
                                global_pool = False,
                                output_stride = 16)
        net = slim.conv2d_transpose(net, num_classes, 31, 16, scope='upscale')
    net = tf.identity(net, 'logits')
    return net, 16

def resnet_tiny (inputs, num_classes=2, scope ='resnet_tiny'):
    blocks = [ 
        resnet_utils.Block('block1', resnet_v1.bottleneck,
                           [(64, 32, 1)] + [(64, 32, 2)]),
        resnet_utils.Block('block2', resnet_v1.bottleneck,
                           [(128, 64, 1)] + [(128, 64, 2)]),
        resnet_utils.Block('block3', resnet_v1.bottleneck,
                           [(256, 64, 1)] + [(128, 64, 2)]),
        resnet_utils.Block('block4', resnet_v1.bottleneck, [(128, 64, 1)])
    	]   
    net,_ = resnet_v1.resnet_v1(
        inputs, blocks,
        # all parameters below can be passed to resnet_v1.resnet_v1_??
        num_classes = None,       # don't produce final prediction
        global_pool = False,       # produce 1x1 output, equivalent to input of a FC layer
        output_stride = 16,
        include_root_block=True,
        reuse=False,              # do not re-use network
        scope=scope)
    net = slim.conv2d_transpose(net, num_classes, 31, 16, scope='upscale')
    net = tf.identity(net, 'logits')
    return net, 16

