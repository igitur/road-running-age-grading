# Releasing and publishing

The version is not stored in any file. `setuptools-scm` takes it from the git tag,
so a release is a tag and nothing else:

```console
$ git tag v0.0.2 && git push origin v0.0.2
```

That push runs [the release workflow](../.github/workflows/release.yml), which
builds, tests, publishes a GitHub release, and — once enabled — publishes the same
artefacts to PyPI. No version bump commit, no chance of a tag and a version
disagreeing, and no way to ship an untagged commit by accident: an untagged build
gets a version like `0.1.dev21+ga620381a3`, which is not publishable.

## What a release contains

| Asset | What it is |
| --- | --- |
| `brrag-<version>-py3-none-any.whl` | The library, the CLI, and the 22-event × 96-age tables for four editions, inside the package. 39 kB. |
| `brrag-<version>.tar.gz` | The source distribution. |
| `brrag-<version>-excel.zip` | The add-in and the workbook that demonstrates it, as one download: `road_running_age_grading.xll` (1 334 784 B, PE32+ x86-64, built in CI) and `age-grading-sample.xlsx` (the workbook from `xll/examples/`, rebuilt and compared with the committed copy at that tag). Unzip both into a folder, then add the `.xll` through **File → Options → Add-ins → Go → Browse**. |
| `SHA256SUMS` | Digests of the three above. |

The `.xll` is cross-compiled on the runner with mingw-w64 against the `xll`
framework **pinned to commit `481178b`**, with
[xll-mingw-portability.patch](../xll/patches/xll-mingw-portability.patch) applied —
the same recipe as `make -C xll xll` locally. The link carries
`-Wl,--no-insert-timestamp` and the compile carries `-ffile-prefix-map` for both
the framework and the source tree, so the binary holds neither a build time nor an
absolute path. That makes it reproducible: the released `.xll` (1 334 784 B,
sha256 `27285a9d…`) is byte-identical to `make -C xll xll` of the same commit on a
different machine, from a framework checked out in a different directory. The one
input that still changes the bytes is the compiler, so the workflow prints
`x86_64-w64-mingw32-g++ --version`; compare hashes only against a build made with
that compiler (this release: gcc 13-win32).

The workbook's twelve live formulas need the add-in loaded; without it they show
`#NAME?`. It is a demonstration, not a data file.

## What the workflow does

1. **build** — full clone (`fetch-depth: 0`, or setuptools-scm sees no tags),
   `python -m build`, then two gates:
   * **the version must be the tag** — `v0.0.2` must produce `brrag-0.0.2`,
     otherwise the run fails rather than publishing something mislabelled;
   * **the wheel must carry its own tables** — `tools/wheel_smoke.py` installs
     the wheel into a fresh venv, runs from `/tmp` so the source-tree fallback
     cannot answer for it, and checks eight editions, three known grades, the
     inverse, an out-of-range refusal and the console script;
   * **the add-in must build and export** — mingw-w64 cross-compiles it, `make
     -C xll verify` fails if any symbol named in `road_running_age_grading.def`
     is missing from the PE export table, and the build asserts the binary names
     all twelve `RRAG.*` functions and imports system DLLs only.
2. **github-release** — `sha256sum` over the assets, then `gh release create
   --generate-notes --verify-tag`. If a release for that tag already exists the
   job **fails** instead of overwriting it: bump the version rather than reuse a
   tag someone may already have linked.
3. **pypi** — trusted publishing, gated on the repository variable
   `PYPI_ENABLED` (see below). On success it polls the PyPI JSON API until the
   version is really listed, so a green run means "downloadable", not "uploaded".

## PyPI: the one-time setup

Publishing uses **trusted publishing** (OpenID Connect), so there is no token and
no secret in the repository. PyPI verifies the workflow's identity instead.

1. Sign in at <https://pypi.org> and open
   **Account settings → Publishing → Add a pending publisher**.
2. Fill it in exactly:

   | Field | Value |
   | --- | --- |
   | PyPI Project Name | `brrag` |
   | Owner | `igitur` |
   | Repository name | `road-running-age-grading` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. Flip the switch in the repository:

   ```console
   $ gh variable set PYPI_ENABLED --body true -R igitur/road-running-age-grading
   ```

The `environment: pypi` in the workflow is part of that identity — the name must
match the pending publisher exactly. Until the variable is set, the publish job
reports *skipped* (with `PYPI_ENABLED != 'true'` in the run summary) and the
release still happens; nothing is lost by publishing to GitHub first.

### If you would rather use an API token

Trusted publishing is the better default — nothing to leak, nothing to rotate.
A token also works: create one at **Account settings → API tokens**, scope it to
the `brrag` project, store it as the secret `PYPI_API_TOKEN`, and replace the
publish step with

```yaml
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

## Rehearsing without publishing

`workflow_dispatch` on a branch builds and tests everything but publishes
nothing (there is no tag, so both publishing jobs are skipped). Use it to check a
change to `pyproject.toml` before tagging:

```console
$ gh workflow run release.yml -R igitur/road-running-age-grading
```

## Publishing a version that never got published

If the GitHub release exists but the PyPI job was skipped, tagging again is not
the answer — the tag and the release already exist and the release job deliberately
refuses to overwrite. Re-run the existing run instead, which retries only the
failed/skipped jobs:

```console
$ gh run rerun <run-id> --failed -R igitur/road-running-age-grading
```

## After a release

* `pip install brrag` picks up the new version within a minute or two; the
  `pypi` job's final step has already confirmed the JSON API lists it.
* If a release is broken, **yank** rather than delete (delete only frees the
  filename; installs that already resolved it stay resolvable):
  **Manage → Releases → Yank** on PyPI. Then fix, bump and tag again.
* Bump the workbook's expectation only if the *tables* changed: the sample
  workbook and `docs/` quote 2025 numbers, and a new edition is a documentation
  change, not a packaging one (see
  [09-history.md](09-history.md#checklist-for-the-next-revision)).

## The table data inside the package

`data/mldr_road.json` is derived from the published calculator page by
`tools/extract_tables.py`. The wheel needs its own copy, so
`brrag/data/mldr_road.json` is a byte-identical duplicate:

```console
$ make pkgdata    # copy data/mldr_road.json -> brrag/data/mldr_road.json
```

`make check` (and therefore CI on every push) fails if the two ever differ, so a
table revision cannot reach a release with only half of the update applied.
`brrag.core.DEFAULT_DATA` prefers the packaged copy and only falls back to
`../data/` when running from a checkout.
