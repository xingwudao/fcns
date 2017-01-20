#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import time
from tqdm import tqdm
import numpy as np
import tensorflow as tf
import tensorflow.contrib.slim as slim
from tensorflow.contrib.layers.python.layers import utils
# RESNET: import these for slim version of resnet
import picpac
import nets

BATCH = 1

flags = tf.app.flags
FLAGS = flags.FLAGS
flags.DEFINE_string('db', 'db', '')
flags.DEFINE_string('val', None, '')
flags.DEFINE_string('net', 'simple', '')
flags.DEFINE_string('opt', 'adam', '')
flags.DEFINE_float('learning_rate', 0.01, 'Initial learning rate.')
flags.DEFINE_bool('decay', False, '')
flags.DEFINE_float('decay_rate', 10000, '')
flags.DEFINE_float('decay_steps', 0.9, '')
flags.DEFINE_float('momentum', 0.99, 'Initial learning rate.')
flags.DEFINE_string('model', 'model', 'Directory to put the training data.')
flags.DEFINE_string('resume', None, '')
flags.DEFINE_integer('max_steps', 200000, '')
flags.DEFINE_integer('epoch_steps', 100, '')
flags.DEFINE_integer('val_epochs', 200, '')
flags.DEFINE_integer('ckpt_epochs', 200, '')
flags.DEFINE_string('log', None, '')
flags.DEFINE_integer('max_summary_images', 20, '')
flags.DEFINE_integer('channels', 1, '')

# clip array to match FCN stride
def clip (v, stride):
    _, H, W, _ = v.shape
    lH = H // stride * stride
    oH = (H - lH)//2
    lW = W // stride * stride
    oW = (W - lW)//2
    return v[:, oH:(oH+lH), oW:(oW+lW),:]

def logits2prob (v, scope='logits2prob', scale=None):
    with tf.name_scope(scope):
        shape = tf.shape(v)    # (?, ?, ?, 2)
        # softmax
        v = tf.reshape(v, (-1, 2))
        v = tf.nn.softmax(v)
        v = tf.reshape(v, shape)
        # keep prob of 1 only
        v = tf.slice(v, [0, 0, 0, 1], [-1, -1, -1, -1])
        # remove trailing dimension of 1
        v = tf.squeeze(v, axis=[3])
        if scale:
            v *= scale
    return v


def fcn_loss (logits, labels):
    logits = tf.reshape(logits, (-1, 2))
    labels = tf.to_int32(labels)    # float from picpac
    labels = tf.reshape(labels, (-1,))
    xe = tf.nn.sparse_softmax_cross_entropy_with_logits(logits, labels)
    loss = tf.reduce_mean(xe, name='xe')
    return loss, [loss] #, [loss, xe, norm, nz_all, nz_dim]

def main (_):
    try:
        os.makedirs(FLAGS.model)
    except:
        pass
    assert FLAGS.db and os.path.exists(FLAGS.db)

    picpac_config = dict(seed=2016,
                #loop=True,
                shuffle=True,
                reshuffle=True,
                #resize_width=256,
                #resize_height=256,
                batch=BATCH,
                split=1,
                split_fold=0,
                annotate='json',
                channels=FLAGS.channels,
                stratify=True,
                pert_color1=20,
                pert_angle=20,
                pert_min_scale=0.8,
                pert_max_scale=1.2,
                #pad=False,
                pert_hflip=True,
                pert_vflip=True,
                channel_first=False # this is tensorflow specific
                                    # Caffe's dimension order is different.
                )

    tr_stream = picpac.ImageStream(FLAGS.db, perturb=True, loop=True, **picpac_config)
    val_stream = None
    if FLAGS.val:
        assert os.path.exists(FLAGS.val)
        val_stream = picpac.ImageStream(FLAGS.val, perturb=False, loop=False, **picpac_config)

    X = tf.placeholder(tf.float32, shape=(None, None, None, 1), name="images")
    Y = tf.placeholder(tf.int32, shape=(None, None, None, 1), name="labels")

    logits, stride = getattr(nets, FLAGS.net)(X)
    loss, metrics = fcn_loss(logits, Y)
    metric_names = [x.name[:-2] for x in metrics]

    rate = FLAGS.learning_rate
    if FLAGS.opt == 'adam':
        rate /= 100
    global_step = tf.Variable(0, name='global_step', trainable=False)
    if FLAGS.decay:
        rate = tf.train.exponential_decay(rate, global_step, FLAGS.decay_steps, FLAGS.decay_rate, staircase=True)
    if FLAGS.opt == 'adam':
        optimizer = tf.train.AdamOptimizer(rate)
    elif FLAGS.opt == 'mom':
        optimizer = tf.train.MomentumOptimizer(rate, FLAGS.momentum)
    else:
        optimizer = tf.train.GradientDescentOptimizer(rate)
        pass

    train_op = optimizer.minimize(loss, global_step=global_step)
    summary_writer = None
    train_summaries = tf.constant(1)
    #val_summaries = tf.constant(1)
    if FLAGS.log:
        summary_writer = tf.summary.FileWriter(FLAGS.log, tf.get_default_graph(), flush_secs=20)
        train_summaries = tf.summary.merge_all()
        #val_summaries = tf.summary.merge_all(key='val_summaries')

    init = tf.global_variables_initializer()

    saver = tf.train.Saver()
    config = tf.ConfigProto()
    config.gpu_options.allow_growth=True

    with tf.Session(config=config) as sess:
        sess.run(init)
        if FLAGS.resume:
            saver.restore(sess, FLAGS.resume)
        step = 0
        epoch = 0
        global_start_time = time.time()
        while step < FLAGS.max_steps:
            start_time = time.time()
            avg = np.array([0] * len(metrics), dtype=np.float32)
            for _ in tqdm(range(FLAGS.epoch_steps), leave=False):
                images, labels, _ = tr_stream.next()
                images = clip(images, stride)
                labels = clip(labels, stride)
                feed_dict = {X: images, Y: labels}
                mm, _, summaries = sess.run([metrics, train_op, train_summaries], feed_dict=feed_dict)
                avg += np.array(mm)
                step += 1
                pass
            avg /= FLAGS.epoch_steps
            stop_time = time.time()
            txt = ', '.join(['%s=%.4f' % (a, b) for a, b in zip(metric_names, list(avg))])
            print('step %d: elapsed=%.4f time=%.4f, %s'
                    % (step, (stop_time - global_start_time), (stop_time - start_time), txt))
            if summary_writer:
                summary_writer.add_summary(summaries, step)
            epoch += 1
            if epoch and (epoch % FLAGS.ckpt_epochs == 0):
                ckpt_path = '%s/%d' % (FLAGS.model, step)
                start_time = time.time()
                saver.save(sess, ckpt_path)
                stop_time = time.time()
                print('epoch %d step %d, saving to %s in %.4fs.' % (epoch, step, ckpt_path, stop_time - start_time))
            if epoch and (epoch % FLAGS.val_epochs == 0) and val_stream:
                val_stream.reset()
                avg = np.array([0] * len(metrics), dtype=np.float32)
                cc = 0
                for images, labels, _ in val_stream:
                    images = clip(images, stride)
                    labels = clip(labels, stride)
                    feed_dict = {X: images, Y: labels}
                    mm, = sess.run([metrics], feed_dict=feed_dict)
                    avg += np.array(mm)
                    cc += 1
                avg /= cc
                txt = ', '.join(['%s=%.4f' % (a, b) for a, b in zip(metric_names, list(avg))])
                print('epoch %d step %d, validation %s'
                        % (epoch, step, txt))

            pass
        pass
    if summary_writer:
        summary_writer.close()
    pass

if __name__ == '__main__':
    tf.app.run()

