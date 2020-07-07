***************
Getting started
***************

Installation
============

To install NengoLMU, we recommend using ``pip``.

.. code:: bash

   pip install lmu

Requirements
------------
NengoLMU works with Python 3.5 or later.  ``pip`` will do its best to install
all of the package's requirements when it installs NengoLMU.  However, if anything
goes wrong during this process, you can install the requirements manually and
then try to ``pip install lmu`` again.
See the `Nengo documentation <https://www.nengo.ai/download/>`_
for instructions on installing ``numpy``, and the ``tensorflow``
installation instructions below.

Installing other packages
-------------------------

The above steps will only install NengoLMU's hard dependencies.
Optional NengoLMU features require additional packages to be installed.

- An optional Legendre initializer
  requires SciPy. You can read more about
  this feature in the :ref:`API reference <api-reference-li>`.
- Running the test suite requires
  pytest.
- Building the documentation requires
  Sphinx, NumPyDoc, nengo_sphinx_theme,
  and a few other packages.

These additional dependencies can also be installed
through ``pip`` when installing NengoLMU.

.. code-block:: bash

   pip install lmu[optional]  # Needed to use the Legendre initializer
   pip install lmu[tests]  # Needed to run unit tests
   pip install lmu[docs]  # Needed to build docs
   pip install lmu[all]  # All of the above

Installing TensorFlow
---------------------

NengoLMU is designed to work within TensorFlow. Thus, in addition to installing
the NengoLMU package, you will also need to install a compatible version of
TensorFlow. You may use ``pip install tensorflow`` to install the minimal version
of TensorFlow.

To enable GPU support for TensorFlow, you require CUDA/cuDNN. For this, we recommend
you use `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/>`_
to simplify the installation process. ``conda install tensorflow-gpu`` will install TensorFlow as
well as all the CUDA/cuDNN requirements.  If you run into any problems, see the
`TensorFlow GPU installation instructions <https://www.tensorflow.org/install/gpu>`_
for more details.

It is also possible to build TensorFlow from source. This is significantly
more complicated but allows you to customize the installation to your specific
system configuration, which can improve simulation speeds. See the system specific
instructions below:

* `Instructions for installing TensorFlow on Ubuntu or Mac OS
  <https://www.tensorflow.org/install/source>`_.

* `Instructions for installing on Windows
  <https://www.tensorflow.org/install/source_windows>`_.

In addition to CUDA/cuDNN, TensorFlow's GPU acceleration is only supported with Nvidia GPUs.
Acquiring the appropriate drivers for your Nvidia GPU depends on your system. On Linux, the
correct Nvidia drivers (as of TensorFlow 2.2.0) can be installed via the command sudo apt install
nvidia-driver-440. On Windows, Nvidia drivers can be downloaded from their website.

Next steps
==========

* If you want to learn how to use NengoLMU in your
  models, read through the :ref:`basic usage <basic-usage>` page.
* For a more detailed understanding of the various
  classes and functions in the NengoLMU package,
  you can read through the :ref:`API reference <api-reference>`.
* If you are interested to learn the theoretical background
  behind how the Legendre Memory Unit works, we recommend reading
  `this technical overview <http://compneuro.uwaterloo.ca/files/publications/voelker.2019.lmu.pdf>`_.
* If you would like to see how NengoLMU is incorporated into various
  models, check out our :ref:`examples <examples>`.