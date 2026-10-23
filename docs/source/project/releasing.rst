:orphan:

Making a release
================

Releases are automated via GitHub Actions. Maintainers with repository write
access can create one in these steps.

From ``main``, create an annotated stable
`EffVer <https://effver.org>`_ tag with a ``v`` prefix.
For example (replace the version with the intended release):

.. code-block:: console

   git tag -a v0.0.0 -m 'Version v0.0.0'

Push the tag to the upstream repository:

.. code-block:: console

   git push https://github.com/NVIDIA/sphinx-llm main --tags

The workflow builds the package and publishes it to PyPI using trusted
publishing. Prerelease tags do not publish a release.
See :doc:`contributing` for development setup.
