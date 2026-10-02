# Versioning and releases

How versions are numbered, where the version lives, and how a release is made. The rules are enforced by a GitHub Actions workflow.

## Scheme

[Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`, for example `1.2.1`. Pre-release suffixes are not used.

| Bump | When | Examples |
|---|---|---|
| **MAJOR** | A change that can break existing installations or needs manual action from users | A database change that older versions cannot read, dropping a supported architecture, changing a default so that existing automations or dashboards stop working |
| **MINOR** | New behaviour that is backward compatible | A new page, field, filter or report option |
| **PATCH** | Everything else | Bug fixes, dependency and security updates, documentation, tooling, licence |

Versions up to and including `1.2.0` were prepared before the first public release. Only the rules above apply from then on.

## One source of truth

The version is the `version:` line in [`logbook/config.yaml`](../logbook/config.yaml), written as a quoted string:

```yaml
version: "1.2.2"
```

Home Assistant offers an update when this value changes. Nothing else defines the version, and nothing else needs editing to change it besides the changelog.

## Every change bumps the version

Every change that goes to `main` bumps the version, including documentation-only changes. Home Assistant only offers an update when the number changes, and the automated check below enforces it. A bump causes users to rebuild the image on their device; their data is kept.

## Changelog

[`logbook/CHANGELOG.md`](../logbook/CHANGELOG.md) has one section per version, newest first, with a heading of exactly this form:

```markdown
## 1.2.2

- What changed, in plain language.
```

The first heading must match the version in `config.yaml`. The text of that section becomes the release notes.

## Making a release

1. Make the change.
2. Set the new `version:` in `logbook/config.yaml`.
3. Add the matching `## X.Y.Z` section at the top of `logbook/CHANGELOG.md`.
4. Update any documentation the change affects, in the same commit.
5. Commit and push to `main`.

The workflow does the rest: it checks the version and, if it is new, creates the tag `vX.Y.Z` and a GitHub release titled `X.Y.Z` whose notes are the changelog section. Do not create the tag or release by hand.

## Automated checks

The workflow [`.github/workflows/version.yml`](../.github/workflows/version.yml) runs on every push to `main` and on every pull request that targets it. The logic is in [`.github/scripts/versioning.py`](../.github/scripts/versioning.py), which uses only the Python standard library.

| Check | Fails when |
|---|---|
| Format | `version` is not `MAJOR.MINOR.PATCH` |
| Changelog | The first `## X.Y.Z` heading differs from `version` |
| Already released | The tag `vX.Y.Z` exists on a different commit (the version was not bumped), or the change is a pull request that reuses a released version |
| Not newer | The version is lower than or equal to the highest released tag |

On a push to `main`, when the checks pass and the tag does not exist yet, a second job creates the tag and the release. The jobs use the built-in `GITHUB_TOKEN` with write access only in the release job. The one external action, `actions/checkout`, is pinned to a commit.

To run the check locally from the repository root:

```bash
python .github/scripts/versioning.py check
```

### What a failure means

A failed check on `main` does not undo the push; it is a signal to fix forward with a new commit that bumps the version. Pushes to `main` are not blocked by default. To make the check mandatory, enable branch protection on `main` under **Settings → Branches** and require the `check` status.

## Fixing a mistake

Releases and tags are never moved or deleted to correct a mistake. Publish a new PATCH version that fixes it.
