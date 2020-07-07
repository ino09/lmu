"""
Core classes for the LMU package, including but not limited to
the cell structure, differential equation, and gating.
"""

import numpy as np

from tensorflow.keras import backend as K
from tensorflow.keras import activations, initializers
from tensorflow.keras.initializers import Constant, Initializer
from tensorflow.keras.layers import Layer

from nengolib.signal import Identity, cont2discrete
from nengolib.synapses import LegendreDelay
from scipy.special import legendre


class Legendre(Initializer):
    """
    Initializes weights using Legendre polynomials,
    leveraging scipy's legendre function. This may be used
    for the encoder and kernel initializers.
    """

    def __call__(self, shape, dtype=None):
        if len(shape) != 2:
            raise ValueError(
                "Legendre initializer assumes shape is 2D; but shape=%s" % (shape,)
            )
        # TODO: geometric spacing might be useful too!
        return np.asarray(
            [legendre(i)(np.linspace(-1, 1, shape[1])) for i in range(shape[0])]
        )


class LMUCell(Layer):
    """
    A layer of trainable low-dimensional delay systems.

    Each unit buffers its encoded input
    by internally representing a low-dimensional
    (i.e., compressed) version of the sliding window.

    Nonlinear decodings of this representation,
    expressed by the A and B matrices, provide
    computations across the window, such as its
    derivative, energy, median value, etc (*).
    Note that these decoder matrices can span across
    all of the units of an input sequence.

    By default the window lengths are trained via backpropagation,
    as well as the encoding and decoding weights.

    Optionally, the A and B matrices that implement
    the low-dimensional delay system can be trained as well,
    but these are shared across all of the units in the layer.

    (*) Voelker and Eliasmith (2018). Improving spiking dynamical
    networks: Accurate delays, higher-order synapses, and time cells.
    Neural Computation, 30(3): 569-609.

    (*) Voelker and Eliasmith. "Methods and systems for implementing
    dynamic neural networks." U.S. Patent Application No. 15/243,223.
    Filing date: 2016-08-22.

    Parameters
    ----------
    units : int
        The number of cells the layer will hold. This
        defines the dimensionality of the output vector.
    order : int
        The size of the memory cell. This defines the
        first dimensions of both the memory encorder
        and kernel. It is also used to determine the
        dimensions of the A and B matrices.
    theta : int
        The size of the sliding window, equivalent to
        the number of timesteps the model will process.
        In this context, the sliding window represents
        a dynamic range of data, of fixed size, that will
        be used to predict the value at the next time step.
        If this value is smaller than the size of the input
        sequence, only that number of steps will be represented
        in the A and B matrices at the time of prediction,
        however the entire sequence will still be processed
        in order for information to be projected to and from
        the hidden layer. This value is relative to a timestep
        of 1 second.
    method : string, optional
        The discretization method used to compute the A
        and B matrices. These matrices are used to map
        inputs onto the memory of the network.
    realizer : nengolib.signal, optional
        Determines what state space representation is
        being realized. This will be applied to the A
        and B matrices. Generally, unless you are training
        the A and B matrices, this should remain as
        its default.
    factory : nengolib.synapses, optional
        Determines what LTI is being created. By default,
        this is the A and B matrices. This can also be used
        to produce different realizations for the same LTI.
        For example, using PadeDelay would give a rotation
        of LegendreDelay. In general, this allows you to
        swap out the dynamic primitive for something else
        entirely.
    trainable_input_encoders : bool, optional
        When true, the input encoders will be trained. This
        will allow for the encoders to learn what
        information is relevant to project from the input.
    trainable_hidden_encoders : bool, optional
        When true, the hidden encoders will be trained. This
        will allow for the encoders to learn what
        information is relevant to project from the hidden
        state.
    trainable_memory_encoders : bool, optional
        When true, the memory encoders will be trained. This
        will allow for the encoders to learn what
        information is relevant to project from the memory.
    trainable_input_kernel : bool, optional
        When true, the input kernel will be trained. This
        will allow for the kernel to learn to compute
        nonlinear functions across the memory.
    trainable_hidden_kernel : bool, optional
        When true, the hidden kernel will be trained. This
        will allow for the kernel to learn to compute
        nonlinear functions across the memory.
    trainable_memory_kernel : bool, optional
        When true, the memory kernel will be trained. This
        will allow for the kernel to learn to compute
        nonlinear functions across the memory.
    trainable_A : bool, optional
        When true, the A matrix will be trained via backpropagation,
        though this is generally not necessary as they can be derived.
    trainable_B : bool, optional
        When true, the B matrix will be trained via backpropagation,
        though this is generally not necessary as they can be derived.
    input_encoders_initializer : tf.keras.initializers.Initializer, optional
        The distribution for the input encoder weights initialization.
    hidden_encoders_initializer : tf.keras.initializers.Initializer, optional
        The distribution for the hidden encoder weights initialization.
    memory_encoders_initializer : tf.keras.initializers.Initializer, optional
        The distribution for the memory encoder weights initialization.
    input_kernel_initializer : tf.keras.initializers.Initializer, optional
        The distribution for the input kernel weights initialization.
    hidden_kernel_initializer : tf.keras.initializers.Initializer, optional
        The distribution for the hidden kernel weights initialization.
    memory_kernel_initializer : tf.keras.initializers.Initializer, optional
        The distribution for the memory kernel weights initialization.
    hidden_activation : string, optional
        The activation function to be used in the hidden component of the LMU.

    Attributes
    ----------
    state_size : tuple
        A tuple containing the units and order.
    output_size : int
        A duplicate of the units parameter.
    """

    def __init__(
        self,
        units,
        order,
        theta,  # relative to dt=1
        method="zoh",
        realizer=Identity(),  # TODO: Deprecate?
        factory=LegendreDelay,  # TODO: Deprecate?
        trainable_input_encoders=True,
        trainable_hidden_encoders=True,
        trainable_memory_encoders=True,
        trainable_input_kernel=True,
        trainable_hidden_kernel=True,
        trainable_memory_kernel=True,
        trainable_A=False,
        trainable_B=False,
        input_encoders_initializer="lecun_uniform",
        hidden_encoders_initializer="lecun_uniform",
        memory_encoders_initializer=Constant(0),  # 'lecun_uniform',
        input_kernel_initializer="glorot_normal",
        hidden_kernel_initializer="glorot_normal",
        memory_kernel_initializer="glorot_normal",
        hidden_activation="tanh",
        **kwargs
    ):
        super().__init__(**kwargs)

        self.units = units
        self.order = order
        self.theta = theta
        self.method = method
        self.realizer = realizer
        self.factory = factory
        self.trainable_input_encoders = trainable_input_encoders
        self.trainable_hidden_encoders = trainable_hidden_encoders
        self.trainable_memory_encoders = trainable_memory_encoders
        self.trainable_input_kernel = trainable_input_kernel
        self.trainable_hidden_kernel = trainable_hidden_kernel
        self.trainable_memory_kernel = trainable_memory_kernel
        self.trainable_A = trainable_A
        self.trainable_B = trainable_B

        self.input_encoders_initializer = initializers.get(input_encoders_initializer)
        self.hidden_encoders_initializer = initializers.get(hidden_encoders_initializer)
        self.memory_encoders_initializer = initializers.get(memory_encoders_initializer)
        self.input_kernel_initializer = initializers.get(input_kernel_initializer)
        self.hidden_kernel_initializer = initializers.get(hidden_kernel_initializer)
        self.memory_kernel_initializer = initializers.get(memory_kernel_initializer)

        self.hidden_activation = activations.get(hidden_activation)

        self._realizer_result = realizer(factory(theta=theta, order=self.order))
        self._ss = cont2discrete(
            self._realizer_result.realization, dt=1.0, method=method
        )
        self._A = self._ss.A - np.eye(order)  # puts into form: x += Ax
        self._B = self._ss.B
        self._C = self._ss.C
        assert np.allclose(self._ss.D, 0)  # proper LTI

        # assert self._C.shape == (1, self.order)
        # C_full = np.zeros((self.units, self.order, self.units))
        # for i in range(self.units):
        #     C_full[i, :, i] = self._C[0]
        # decoder_initializer = Constant(
        #     C_full.reshape(self.units*self.order, self.units))

        # TODO: would it be better to absorb B into the encoders and then
        # initialize it appropriately? trainable encoders+B essentially
        # does this in a low-rank way

        # if the realizer is CCF then we get the following two constraints
        # that could be useful for efficiency
        # assert np.allclose(self._ss.B[1:], 0)  # CCF
        # assert np.allclose(self._ss.B[0], self.order**2)

        self.state_size = (self.units, self.order)
        self.output_size = self.units

    def build(self, input_shape):
        """
        Overrides the TensorFlow build function.
        Initializes all the encoders and kernels,
        as well as the A and B matrices for the
        LMUCell.
        """

        input_dim = input_shape[-1]

        # TODO: add regularizers

        self.input_encoders = self.add_weight(
            name="input_encoders",
            shape=(input_dim, 1),
            initializer=self.input_encoders_initializer,
            trainable=self.trainable_input_encoders,
        )

        self.hidden_encoders = self.add_weight(
            name="hidden_encoders",
            shape=(self.units, 1),
            initializer=self.hidden_encoders_initializer,
            trainable=self.trainable_hidden_encoders,
        )

        self.memory_encoders = self.add_weight(
            name="memory_encoders",
            shape=(self.order, 1),
            initializer=self.memory_encoders_initializer,
            trainable=self.trainable_memory_encoders,
        )

        self.input_kernel = self.add_weight(
            name="input_kernel",
            shape=(input_dim, self.units),
            initializer=self.input_kernel_initializer,
            trainable=self.trainable_input_kernel,
        )

        self.hidden_kernel = self.add_weight(
            name="hidden_kernel",
            shape=(self.units, self.units),
            initializer=self.hidden_kernel_initializer,
            trainable=self.trainable_hidden_kernel,
        )

        self.memory_kernel = self.add_weight(
            name="memory_kernel",
            shape=(self.order, self.units),
            initializer=self.memory_kernel_initializer,
            trainable=self.trainable_memory_kernel,
        )

        self.AT = self.add_weight(
            name="AT",
            shape=(self.order, self.order),
            initializer=Constant(self._A.T),  # note: transposed
            trainable=self.trainable_A,
        )

        self.BT = self.add_weight(
            name="BT",
            shape=(1, self.order),  # system is SISO
            initializer=Constant(self._B.T),  # note: transposed
            trainable=self.trainable_B,
        )

        self.built = True

    def call(self, inputs, states):
        """
        Overrides the TensorFlow call function.
        Contains the logic for one LMU step calculation.
        """

        h, m = states

        u = (
            K.dot(inputs, self.input_encoders)
            + K.dot(h, self.hidden_encoders)
            + K.dot(m, self.memory_encoders)
        )

        m = m + K.dot(m, self.AT) + K.dot(u, self.BT)

        h = self.hidden_activation(
            K.dot(inputs, self.input_kernel)
            + K.dot(h, self.hidden_kernel)
            + K.dot(m, self.memory_kernel)
        )

        return h, [h, m]

    def get_config(self):
        """
        Overrides the TensorFlow get_config function.
        Sets the config with the LMUCell parameters.
        """

        config = super().get_config()
        config.update(
            dict(
                units=self.units,
                order=self.order,
                theta=self.theta,
                method=self.method,
                factory=self.factory,
                trainable_input_encoders=self.trainable_input_encoders,
                trainable_hidden_encoders=self.trainable_hidden_encoders,
                trainable_memory_encoders=self.trainable_memory_encoders,
                trainable_input_kernel=self.trainable_input_kernel,
                trainable_hidden_kernel=self.trainable_hidden_kernel,
                trainable_memory_kernel=self.trainable_memory_kernel,
                trainable_A=self.trainable_A,
                trainable_B=self.trainable_B,
                input_encorders_initializer=self.input_encoders_initializer,
                hidden_encoders_initializer=self.hidden_encoders_initializer,
                memory_encoders_initializer=self.memory_encoders_initializer,
                input_kernel_initializer=self.input_kernel_initializer,
                hidden_kernel_initializer=self.hidden_kernel_initializer,
                memory_kernel_initializer=self.memory_kernel_initializer,
                hidden_activation=self.hidden_activation,
            )
        )

        return config


class InputScaled(Initializer):
    """Divides a constant value by the incoming dimensionality."""

    def __init__(self, value=0):
        super(InputScaled, self).__init__()
        self.value = value

    def __call__(self, shape, dtype=None):
        return K.constant(self.value / shape[0], shape=shape, dtype=dtype)


class LMUCellODE(Layer):
    """Variant of LMUCell that supports backprop through the ODE solver."""

    def __init__(
        self,
        units,
        order,
        theta=100,  # relative to dt=1
        method="euler",
        return_states=False,
        realizer=Identity(),
        factory=LegendreDelay,
        trainable_encoders=True,
        trainable_decoders=True,
        trainable_dt=False,
        trainable_A=False,
        trainable_B=False,
        encoder_initializer=InputScaled(1.0),  # TODO
        decoder_initializer=None,  # TODO
        hidden_activation="linear",  # TODO
        output_activation="tanh",  # TODO
        **kwargs
    ):
        super().__init__(**kwargs)

        self.units = units
        self.order = order
        self.theta = theta
        self.method = method
        self.return_states = return_states
        self.realizer = realizer
        self.factory = factory
        self.trainable_encoders = trainable_encoders
        self.trainable_decoders = trainable_decoders
        self.trainable_dt = trainable_dt
        self.trainable_A = trainable_A
        self.trainable_B = trainable_B

        self._realizer_result = realizer(factory(theta=theta, order=self.order))
        self._ss = self._realizer_result.realization
        self._A = self._ss.A
        self._B = self._ss.B
        self._C = self._ss.C
        assert np.allclose(self._ss.D, 0)  # proper LTI

        self.encoder_initializer = initializers.get(encoder_initializer)
        self.dt_initializer = initializers.get(Constant(1.0))

        if decoder_initializer is None:
            assert self._C.shape == (1, self.order)
            C_full = np.zeros((self.units, self.order, self.units))
            for i in range(self.units):
                C_full[i, :, i] = self._C[0]
            decoder_initializer = Constant(
                C_full.reshape(self.units * self.order, self.units)
            )

        self.decoder_initializer = initializers.get(decoder_initializer)
        self.hidden_activation = activations.get(hidden_activation)
        self.output_activation = activations.get(output_activation)

        # TODO: would it be better to absorb B into the encoders and then
        # initialize it appropriately? trainable encoders+B essentially
        # does this in a low-rank way

        # if the realizer is CCF then we get the following two constraints
        # that could be useful for efficiency
        # assert np.allclose(self._ss.B[1:], 0)  # CCF
        # assert np.allclose(self._ss.B[0], self.order**2)

        if not (self.trainable_dt or self.trainable_A or self.trainable_B):
            # This is a hack to speed up parts of the computational graph
            # that are static. This is not a general solution.
            ss = cont2discrete(self._ss, dt=1.0, method=self.method)
            AT = K.variable(ss.A.T)
            B = K.variable(ss.B.T[None, ...])
            self._solver = lambda: (AT, B)

        elif self.method == "euler":
            self._solver = self._euler

        elif self.method == "zoh":
            self._solver = self._zoh

        else:
            raise NotImplementedError("Unknown method='%s'" % self.method)

        self.state_size = self.units * self.order  # flattened
        self.output_size = self.state_size if return_states else self.units

    def build(self, input_shape):
        """
        Initializes various network parameters.
        """

        input_dim = input_shape[-1]

        # TODO: add regularizers

        self.encoders = self.add_weight(
            name="encoders",
            shape=(input_dim, self.units),
            initializer=self.encoder_initializer,
            trainable=self.trainable_encoders,
        )

        self.dt = self.add_weight(
            name="dt",
            shape=(1,),
            initializer=self.dt_initializer,
            trainable=self.trainable_dt,
        )

        self.decoders = self.add_weight(
            name="decoders",
            shape=(self.units * self.order, self.output_size),
            initializer=self.decoder_initializer,
            trainable=self.trainable_decoders,
        )

        self.AT = self.add_weight(
            name="AT",
            shape=(self.order, self.order),
            initializer=Constant(self._A.T),  # note: transposed
            trainable=self.trainable_A,
        )

        self.B = self.add_weight(
            name="B",
            shape=(1, 1, self.order),  # system is SISO
            initializer=Constant(self._B[None, None, :]),
            trainable=self.trainable_B,
        )

        self.I = K.eye(self.order)  # noqa: E741
        self.zero_padding = K.zeros((1, self.order + 1))

        self.built = True

    def _euler(self):
        AT = self.I + self.dt * self.AT
        B = self.dt * self.B
        return (AT, B)

    def _zoh(self):
        M = K.concatenate(
            [
                K.concatenate([K.transpose(self.AT), K.transpose(self.B[0])], axis=1),
                self.zero_padding,
            ],
            axis=0,
        )
        eM = K.tf.linalg.expm(self.dt * M)
        return (
            K.transpose(eM[: self.order, : self.order]),
            K.reshape(eM[: self.order, self.order :], self.B.shape),
        )

    def call(self, inputs, states):
        """
        Contains the logic for one LMU step calculation.
        """

        u = K.dot(inputs, self.encoders)

        x = K.reshape(states[0], (-1, self.units, self.order))

        AT, B = self._solver()

        x = K.dot(x, AT) + B * K.expand_dims(u, -1)

        x = self.hidden_activation(K.reshape(x, (-1, self.units * self.order)))

        y = self.output_activation(K.dot(x, self.decoders))

        return y, [x]


class LMUCellGating(Layer):
    """Variant of LMUCell that supports gating mechanisms."""

    def __init__(
        self,
        units,
        order,
        theta,  # relative to dt=1
        method="zoh",
        realizer=Identity(),
        factory=LegendreDelay,
        trainable_input_encoders=True,
        trainable_hidden_encoders=True,
        trainable_memory_encoders=True,
        trainable_input_kernel=True,
        trainable_hidden_kernel=True,
        trainable_memory_kernel=True,
        trainable_forget_input_kernel=False,
        trainable_forget_hidden_kernel=False,
        trainable_forget_bias=False,
        trainable_A=False,
        trainable_B=False,
        input_encoders_initializer="lecun_uniform",
        hidden_encoders_initializer="lecun_uniform",
        memory_encoders_initializer=Constant(0),  # 'lecun_uniform',
        input_kernel_initializer="glorot_normal",
        hidden_kernel_initializer="glorot_normal",
        memory_kernel_initializer="glorot_normal",
        forget_input_kernel_initializer=Constant(1),
        forget_hidden_kernel_initializer=Constant(1),
        forget_bias_initializer=Constant(0),
        hidden_activation="tanh",
        input_activation="linear",
        gate_activation="linear",
        **kwargs
    ):
        super().__init__(**kwargs)

        self.units = units
        self.order = order
        self.theta = theta
        self.method = method
        self.realizer = realizer
        self.factory = factory
        self.trainable_input_encoders = trainable_input_encoders
        self.trainable_hidden_encoders = trainable_hidden_encoders
        self.trainable_memory_encoders = trainable_memory_encoders
        self.trainable_input_kernel = trainable_input_kernel
        self.trainable_hidden_kernel = trainable_hidden_kernel
        self.trainable_memory_kernel = trainable_memory_kernel
        self.trainable_forget_input_kernel = (trainable_forget_input_kernel,)
        self.trainable_forget_hidden_kernel = trainable_forget_hidden_kernel
        self.trainable_forget_bias = trainable_forget_bias
        self.trainable_A = trainable_A
        self.trainable_B = trainable_B

        self.input_encoders_initializer = initializers.get(input_encoders_initializer)
        self.hidden_encoders_initializer = initializers.get(hidden_encoders_initializer)
        self.memory_encoders_initializer = initializers.get(memory_encoders_initializer)
        self.input_kernel_initializer = initializers.get(input_kernel_initializer)
        self.hidden_kernel_initializer = initializers.get(hidden_kernel_initializer)
        self.memory_kernel_initializer = initializers.get(memory_kernel_initializer)
        self.forget_input_kernel_initializer = initializers.get(
            forget_input_kernel_initializer
        )
        self.forget_hidden_kernel_initializer = initializers.get(
            forget_hidden_kernel_initializer
        )
        self.forget_bias_initializer = initializers.get(forget_bias_initializer)

        self.hidden_activation = activations.get(hidden_activation)
        self.input_activation = activations.get(input_activation)
        self.gate_activation = activations.get(gate_activation)

        self._realizer_result = realizer(factory(theta=theta, order=self.order))
        self._ss = cont2discrete(
            self._realizer_result.realization, dt=1.0, method=method
        )
        self._A = self._ss.A - np.eye(order)  # puts into form: x += Ax
        self._B = self._ss.B
        self._C = self._ss.C
        assert np.allclose(self._ss.D, 0)  # proper LTI

        # assert self._C.shape == (1, self.order)
        # C_full = np.zeros((self.units, self.order, self.units))
        # for i in range(self.units):
        #     C_full[i, :, i] = self._C[0]
        # decoder_initializer = Constant(
        #     C_full.reshape(self.units*self.order, self.units))

        # TODO: would it be better to absorb B into the encoders and then
        # initialize it appropriately? trainable encoders+B essentially
        # does this in a low-rank way

        # if the realizer is CCF then we get the following two constraints
        # that could be useful for efficiency
        # assert np.allclose(self._ss.B[1:], 0)  # CCF
        # assert np.allclose(self._ss.B[0], self.order**2)

        self.state_size = (self.units, self.order)
        self.output_size = self.units

    def build(self, input_shape):
        """
        Initializes various network parameters.
        """

        input_dim = input_shape[-1]

        # TODO: add regularizers

        self.input_encoders = self.add_weight(
            name="input_encoders",
            shape=(input_dim, 1),
            initializer=self.input_encoders_initializer,
            trainable=self.trainable_input_encoders,
        )

        self.hidden_encoders = self.add_weight(
            name="hidden_encoders",
            shape=(self.units, 1),
            initializer=self.hidden_encoders_initializer,
            trainable=self.trainable_hidden_encoders,
        )

        self.memory_encoders = self.add_weight(
            name="memory_encoders",
            shape=(self.order, 1),
            initializer=self.memory_encoders_initializer,
            trainable=self.trainable_memory_encoders,
        )

        self.input_kernel = self.add_weight(
            name="input_kernel",
            shape=(input_dim, self.units),
            initializer=self.input_kernel_initializer,
            trainable=self.trainable_input_kernel,
        )

        self.hidden_kernel = self.add_weight(
            name="hidden_kernel",
            shape=(self.units, self.units),
            initializer=self.hidden_kernel_initializer,
            trainable=self.trainable_hidden_kernel,
        )

        self.memory_kernel = self.add_weight(
            name="memory_kernel",
            shape=(self.order, self.units),
            initializer=self.memory_kernel_initializer,
            trainable=self.trainable_memory_kernel,
        )

        self.forget_input_kernel = self.add_weight(
            name="forget_input_kernel",
            shape=(input_dim, self.order),
            initializer=self.forget_input_kernel_initializer,
            trainable=self.trainable_forget_input_kernel,
        )

        self.forget_hidden_kernel = self.add_weight(
            name="forget_hidden_kernel",
            shape=(self.units, self.order),
            initializer=self.forget_input_kernel_initializer,
            trainable=self.trainable_forget_input_kernel,
        )

        self.forget_bias = self.add_weight(
            name="forget_bias",
            shape=(1, self.order),
            initializer=self.forget_bias_initializer,
            trainable=self.trainable_forget_bias,
        )

        self.AT = self.add_weight(
            name="AT",
            shape=(self.order, self.order),
            initializer=Constant(self._A.T),  # note: transposed
            trainable=self.trainable_A,
        )

        self.BT = self.add_weight(
            name="BT",
            shape=(1, self.order),  # system is SISO
            initializer=Constant(self._B.T),  # note: transposed
            trainable=self.trainable_B,
        )

        self.built = True

    def call(self, inputs, states):
        """
        Contains the logic for one LMU step calculation.
        """

        h, m = states

        u = self.input_activation(
            (
                K.dot(inputs, self.input_encoders)
                + K.dot(h, self.hidden_encoders)
                + K.dot(m, self.memory_encoders)
            )
        )

        f = self.gate_activation(
            K.dot(inputs, self.forget_input_kernel)
            + K.dot(h, self.forget_hidden_kernel)
            + self.forget_bias
        )

        m = m + K.dot(m, self.AT) + f * K.dot(u, self.BT)

        h = self.hidden_activation(
            K.dot(inputs, self.input_kernel)
            + K.dot(h, self.hidden_kernel)
            + K.dot(m, self.memory_kernel)
        )

        return h, [h, m]
