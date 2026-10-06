# Contributing

## Signing Your Work

* Contributors outside the NVIDIA GitHub organization must "sign-off" on their
  commits. This certifies
  that the contribution is your original work, or you have rights to submit it
  under the same license, or a compatible license.

  * Sign off every commit you author, rather than just one commit in a pull
    request. The standard [DCO App](https://github.com/dcoapp/app) checks each
    ordinary commit independently, with exceptions for bots and merge commits.
    NVIDIA organization members are exempt from the check when GitHub verifies
    their commit's cryptographic signature; unverified member commits still need
    a sign-off. Cryptographic signing and DCO sign-off are separate.

* To sign off on a commit you simply use the `--signoff` (or `-s`) option when
  committing your changes:

  ```bash
  git commit -s -m "Add cool feature."
  ```

  This will append the following to your commit message:

  ```text
  Signed-off-by: Your Name <your@email.com>
  ```

* When squash merging, retain a valid `Signed-off-by` line from every external
  contributor in the final commit message. Preserve the original commit messages
  or copy their sign-off lines into the squash message. Co-author attribution
  alone does not certify the DCO. Maintainers must review contributor sign-offs:
  the App accepts an author or committer identity and does not validate every
  `Co-authored-by` identity, so a passing check alone does not prove that every
  contributor personally signed off.

* The configuration in `.github/dco.yml` applies on the default branch. A
  repository administrator must ensure the organization's DCO App is enabled
  for this repository and make its `DCO` check required in branch protection or
  a ruleset. For squash merges, use **Default to pull request title and commit
  details** (`squash_merge_commit_message: COMMIT_MESSAGES`) and verify the final
  message retains every external contributor's sign-off. The App cannot prevent
  a maintainer from removing those lines in the merge dialog. Its write-access
  override is a trusted-maintainer bypass, not a contributor sign-off.

* Full text of the DCO:

  ```text
    Developer Certificate of Origin
    Version 1.1

    Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
    1 Letterman Drive
    Suite D4700
    San Francisco, CA, 94129

    Everyone is permitted to copy and distribute verbatim copies of this
    license document, but changing it is not allowed.
  ```

  ```text
    Developer's Certificate of Origin 1.1

    By making a contribution to this project, I certify that:

    (a) The contribution was created in whole or in part by me and I have the
    right to submit it under the open source license indicated in the file; or

    (b) The contribution is based upon previous work that, to the best of my
    knowledge, is covered under an appropriate open source license and I have
    the right under that license to submit that work with modifications,
    whether created in whole or in part by me, under the same open source
    license (unless I am permitted to submit under a different license), as
    indicated in the file; or

    (c) The contribution was provided directly to me by some other person who
    certified (a), (b) or (c) and I have not modified it.

    (d) I understand and agree that this project and the contribution are
    public and that a record of the contribution (including all personal
    information I submit with it, including my sign-off) is maintained
    indefinitely and may be redistributed consistent with this project or the
    open source license(s) involved.
  ```
