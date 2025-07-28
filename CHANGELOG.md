# Changelog

## [0.11.1-1] - 2025-07-03

### Fixed

* Fix issues found in the production probe

## [0.11.0-1] - 2025-06-24

### Added

* Support registry.egi.eu images

## [0.10.2-1] - 2024-12-19

### Changed

* Better error handling for novaprobe

## [0.8.0-1] - 2022-12-07

### Added

* ARGO-4438 Replace cloudinfo.py probe with newer one

### Changed

* ARGO-4434 Refactor check_perun probe to take cert and key as argument

## [0.7.1-1] - 2022-10-21

### Changed

* AO-710 Remove support for two OIDC access tokens

## [0.7.0-1] - 2022-09-05

### Changed

* Updates from the devel branch of old repo
* AO-651 Harmonize EGI probes

## [0.6.3-1] - 2022-06-24

### Added

* Add second token argument to novaprobe and swiftprobe

## [0.6.2-1] - 2021-06-16

### Fixed

* Fix robot cert path in check_perun

## [0.6.1-1] - 2021-06-15

### Added

* Add region support to novaprobe

## [0.6.0-1] - 2021-01-13

### Added

* New probe for cloud info provider

## [0.5.2-1] - 2020-04-08

### Added

* Add swiftprobe.py

## [0.5.1-1] - 2020-03-31

### Added

* Add EOSC-hub acknowledgement

### Changed

* vary spec dependency according to Centos version

### Fixed

* Fix perun.cesnet.cz address

## [0.5.0-1] - 2019-10-03

### Added

* Support for new version of cloudkeeper

### Changed

* Refactor authentication

## [0.4.0-1] - 2019-09-05

### Changed

* Reduce default timeout for VMs to 300s
* Clean leftover VMs
* Do not try to use the certificate when not needed

## [0.3.0-1] - 2019-04-17

### Added

* Add network handling

### Changed

* Delete VM to avoid leaving resources at sites
* Remove cdmi probe
* Enforce certificate validation

## [0.2.0-1] - 2019-02-07

### Added

* Add support for both X509 and OIDC in openstack probe
* Add support for Keystone V3
* Add support for using AppDB image in openstack probe

## [0.1.7-1] - 2017-12-08

### Changed

* graceful clean-up for OCCI compute probe

## [0.1.6-1] - 2017-11-20

### Changed

* novaprobe: remove hardcoded port check in token suffix
* novaprobe: ARGO-948 Access token parameter should be file

## [0.1.5-1] - 2017-08-30

### Added

* novaprobe: added support for OIDC tokens by Enol Fernandez

### Changed

* novaprobe: use of ids insteads of urls for flavors and image by Enol Fernandez

## [0.1.3-1] - 2016-12-13

### Changed

* refactored keystone token and cert check code

## [0.1.1-7] - 2016-11-22

### Changed

* Probes location aligned with guidelines

## [0.1.0-6] - 2016-05-13

### Added

* cdmiprobe: add support for printing error msgs from packed exceptions

### Changed

* cdmiprobe: wait some time before next operation
* cdmiprobe: fetched token implies that we have supported CDMI Specification version
* cdmiprobe: merged improvements with proper cleanup procedure by Enol Fernandez

## [0.1.0-5] - 2026-01-19

### Changed

* remove Py2.6 deprecations in cdmiprobe and novaprobe

## [0.1.0-4] - 2015-10-06

### Fixed

* novaprobe: debugging helper leftover removed

## [0.1.0-3] - 2015-10-02

### Changed

* novaprobe: only HTTPS endpoints allowed

## [0.1.0-2] - 2015-09-23

### Added

* cdmiprobe: handle case when endpoint disabled SSLv3
* novaprobe: added image and flavor cmd options

### Fixed

* novaprobe: no roundtrip, keystone service is given directly

## [0.1.0-1] - 2015-09-18

### Added

* Initial version of EGI FedCloud probes for Nagios
