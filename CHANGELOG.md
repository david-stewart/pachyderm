# Pachyderm Changelog

Changelog based on the [format here](https://keepachangelog.com/en/1.0.0/).

## [1.2] - 17 December 2018

### Added

- Include `--ignore-missing-includes` when running `mypy` automatically. See: `0ac7d0bd`.
- Full type annotations for the package. See: `a83372b1`.

### Changed

- Fully updated API naming scheme to follow python conventions. See: `cd097f3b`, `c7bedc6b`, `68048970`, and
  `7d8b1ca9`.
- Remove `pkgconfig` workaround introduced in `4a3c6216` since `python-lz4` merged in an alternative
  [approach](https://github.com/python-lz4/python-lz4/pull/160) to workaround the issue. See: `755c276a`.

## [1.1] - 15 December 2018

### Added

- Added `mypy` to Travis CI checks. See: `2c6f7dc0`.

### Changed

- Reworked iteration over analysis dictionaries. See: `0ead6db8`.
- Updated overwatch-base python version. See: `39fede7e`.

### Fixed

- Existing typing issues identified by `mypy`.

## [1.0] - 10 December 2018

### Added

- `Histogram1D` class moved from the `reaction_plane_fit` package to `pachyderm`. See: `89d2eaa3.`
- Added `uproot` dependency and add fix for `lz4` issue that is caused by ROOT. See: `89d2eaa3` and
  `4a3c6216`.
- version info is now available in the package by simply typing `import pachyderm; pachyderm.version_info`.
  See: `32ff4f96`.

### Changed

- Moved histogram functionality from `utils` to a new `histogram` module. This module also contains the added
  `Histogram1D` class (see above). See: `89d2eaa3`.

## [0.9] - 10 December 2018

- Initial release, with most of the development performed in
  [alice-yale-dev](https://github.com/ALICEYale/alice-yale-dev), and a bit in
  [alice-jet-hadron](https://github.com/raymondEhlers/alice-jet-hadron).
