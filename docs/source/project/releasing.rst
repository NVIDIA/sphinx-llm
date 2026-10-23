Making a release
================

We publish releases through GitHub Actions. If you have write access to the
repository, you can start a release by creating and pushing an annotated tag.

Create a release tag
--------------------

Start from ``main`` and choose a stable
`EffVer <https://effver.org>`_ version. Tags need a ``v`` prefix.
For example, replace the version below with the release you're preparing:

.. code-block:: console

   git tag -a v0.0.0 -m 'Version v0.0.0'

Publish the tag
---------------

Push to the upstream repository:

.. code-block:: console

   git push https://github.com/NVIDIA/sphinx-llm main --tags

The release workflow builds the package and publishes it to PyPI using trusted
publishing. Prerelease tags don't publish a release.
For local development and checks before you release, see :doc:`contributing`.
