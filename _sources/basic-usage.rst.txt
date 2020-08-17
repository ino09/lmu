.. _basic-usage:

***********
Basic usage
***********

The standard Legendre Memory Unit (LMU) cell
implementation in NengoLMU is defined in the
``lmu.LMUCell`` class. The following code creates
a new LMU layer:

.. testcode::

   import lmu
   
   cells = lmu.LMUCell(
       units=10,
       order=256,
       theta=784,
   )

Note that these are arbitrary values for ``units``, ``order``, 
and ``theta``. ``units`` represents the dimension of the output
vector. ``order`` represents the dimension of the memory cell. 
And ``theta`` represents the dimension of the sliding window.
To learn more about these parameters, you can check the
:ref:`API reference <api-reference-lc>`.

Creating NengoLMU layers
------------------------

The ``LMUCell`` class functions as a standard
TensorFlow layer. Because the LMU is a recurrent
neural network, it needs to be wrapped with a
TensorFlow recurrent layer. Note that NengoLMU
is meant to be used within a TensorFlow model.

.. testcode::

   from tensorflow.keras.models import Sequential
   from tensorflow.keras.layers import RNN

   model = Sequential()
   layer = RNN(cells)
   model.add(layer)

Customizing parameters
----------------------

The ``LMUCell`` is designed to be easy to use and
be integrated seamlessly into your TensorFlow
models. However, for users looking to optimize
their use of the ``LMUCell``, there are additional
parameters that can be modified.

.. testcode::

    from nengolib.signal import Identity
    from nengolib.synapses import LegendreDelay

    custom_cells = lmu.LMUCell(
        units=10,
        order=256,
        theta=784,
        method="zoh",
        hidden_activation="tanh",
    )

The ``method`` parameter specifies the
discretization method that will be used to compute
the ``A`` and ``B`` matrices. By default, this parameter is
set to ``zoh`` (zero-order-hold). This is generally the best
option for input signals that are held constant
between time steps, which is a common use case for
sequential data (e.g. feeding in a sequence of
pixels like in the psMNIST task).

The ``hidden_activation`` parameter specifies the
final non-linearity that gets applied to the
output. By default, this parameter is set to
``tanh``. This is mainly done so that outputs
are symmetric about zero and saturated to
``[-1, 1]``, which betters stability. Though,
other non-linearities like ``ReLU`` work well too.

Tuning these parameters can lead to optimized
performance. As an example, using ``euler`` as the
discretization method results in an LMU configuration
that is easier to implement in physical hardware and
is also more amenable in a model where ``theta`` is
trained or controlled on the fly.

Customizing trainability
------------------------

The ``LMUCell`` allows users to choose which
encoders and kernels they want to be trained.
By default, every encoder and kernel is
trainable, while the ``A`` and ``B`` matrices
are not.

.. testcode::

    custom_cells = lmu.LMUCell(
        units=10,
        order=256,
        theta=784,
        trainable_input_encoders=True,
        trainable_hidden_encoders=True,
        trainable_memory_encoders=True,
        trainable_input_kernel=True,
        trainable_hidden_kernel=True,
        trainable_memory_kernel=True,
        trainable_A=False,
        trainable_B=False,
    )

These trainability flags may be configured however
you would like. The need for specific weights
to be trained will vary depending on the task
being modelled and the design of the network.

Customizing initializers
------------------------

The ``LMUCell`` allows users to customize
the various initializers for its encoders
and kernels. These define the distributions
from which the initial values for the encoder
or kernel weights will be drawn.

.. testcode::

    from tensorflow.keras.initializers import Constant

    custom_cells = lmu.LMUCell(
        units=10,
        order=256,
        theta=784,
        input_encoders_initializer=Constant(1),
        hidden_encoders_initializer=Constant(0),
        memory_encoders_initializer=Constant(0),
        input_kernel_initializer=Constant(0),
        hidden_kernel_initializer=Constant(0),
        memory_kernel_initializer="glorot_normal",
    )

These initializers may be configured using
a variety of distributions
(`see TensorFlow initializers documentation here <https://www.tensorflow.org/api_docs/python/tf/keras/initializers>`_).
Generally, we recommend a ``glorot_uniform``
distribution for feed-forward weights, and an
``orthogonal`` distribution for recurrent weights.