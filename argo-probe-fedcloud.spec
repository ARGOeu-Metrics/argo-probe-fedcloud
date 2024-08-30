Summary:       ARGO probes for EGI FedCloud services
Name:          argo-probe-fedcloud
Version:       0.10.1
Release:       1%{?dist}
License:       ASL 2.0
Group:         Network/Monitoring
Source0:       argo-probe-fedcloud-%{version}.tar.gz
BuildRoot:     %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch:     noarch
Requires:      python3
Requires:      python3-requests
Requires:      python3-novaclient
Requires:      python3-keystoneclient
Requires:      python3-neutronclient
Requires:      python3-glanceclient
Requires:      python3-keystoneauth1
BuildRequires: python3-devel
BuildRequires: pyproject-rpm-macros
BuildRequires: python3-wheel
%description
Monitoring probes for EGI Fedcloud

%prep
%autosetup -p1 -n argo-probe-fedcloud-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files '*' +auto
install --mode 755 src/bin/*  ${RPM_BUILD_ROOT}%{_bindir}

%clean
rm -rf $RPM_BUILD_ROOT

%files -n argo-probe-fedcloud -f %{pyproject_files}
%{_bindir}/check_fedcloud_accnt

%changelog
* Thu Aug 29 2024 Katarina Zailac <kzailac@srce.hr> - 0.10.1-1%{?dist}
- Do not skip probe if server from other argo
* Wed Aug 14 2024 Katarina Zailac <kzailac@srce.hr> - 0.10.0-1%{?dist}
- ARGO-4683 Migrate from Nagios::Plugin to Monitoring::Plugin argo-probe-fedcloud
- AO-974 Create Jenkinsfile for argo-probe-fedcloud
* Mon Apr 8 2024 Enol Fernandez <enol.fernandez@egi.eu> - 0.9.0-1%{?dist}
- Move to python3 and rocky9
* Wed Dec 7 2022 Katarina Zailac <kzailac@srce.hr> - 0.8.0-1%{?dist}
- ARGO-4438 Replace cloudinfo.py probe with newer one
- ARGO-4434 Refactor check_perun probe to take cert and key as argument
* Fri Oct 21 2022 Katarina Zailac <kzailac@srce.hr> - 0.7.1-1%{?dist}
- AO-710 Remove support for two OIDC access tokens
* Mon Sep 5 2022 Katarina Zailac <kzailac@srce.hr> - 0.7.0-1%{?dist}
- Updates from the devel branch of old repo
- AO-651 Harmonize EGI probes
* Fri Jun 24 2022 Katarina Zailac <kzailac@srce.hr> - 0.6.3-1%{?dist}
- Add second token argument to novaprobe and swiftprobe
* Wed Jun 16 2021 Emir Imamagic <eimamagi@srce.hr> - 0.6.2-1%{?dist}
- Fix robot cert path in check_perun
* Tue Jun 15 2021 Katarina Zailac <kzailac@srce.hr> - 0.6.1-1%{?dist}
- Add region support to novaprobe
* Wed Jan 13 2021 Katarina Zailac <kzailac@srce.hr> - 0.6.0-1%{?dist}
- New probe for cloud info provider
* Wed Apr 8 2020 Katarina Zailac <kzailac@srce.hr> - 0.5.2-1%{?dist}
- Add swiftprobe.py
* Tue Mar 31 2020 Daniel Vrcic <dvrcic@srce.hr> - 0.5.1-1%{?dist}
- Fix perun.cesnet.cz address
- Add EOSC-hub acknowledgement
- vary spec dependency according to Centos version
* Thu Oct 3 2019 Emir Imamagic <eimamagi@srce.hr> - 0.5.0-1%{?dist}
- Support for new version of cloudkeeper
- Refactor authentication
* Thu Sep 5 2019 Emir Imamagic <eimamagi@srce.hr> - 0.4.0-1%{?dist}
- Reduce default timeout for VMs to 300s
- Clean leftover VMs
- Do not try to use the certificate when not needed
* Wed Apr 17 2019 Emir Imamagic <eimamagi@srce.hr> - 0.3.0-1%{?dist}
- Add network handling
- Delete VM to avoid leaving resources at sites
- Remove cdmi probe
- Enforce certificate validation
* Thu Feb 7 2019 Emir Imamagic <eimamagi@srce.hr> - 0.2.0-1%{?dist}
- Add support for both X509 and OIDC in openstack probe
- Add support for Keystone V3
- Add support for using AppDB image in openstack probe
* Fri Dec 8 2017 Daniel Vrcic <dvrcic@srce.hr> - 0.1.7-1%{?dist}
- graceful clean-up for OCCI compute probe
* Mon Nov 20 2017 Daniel Vrcic <dvrcic@srce.hr> - 0.1.6-1%{?dist}
- novaprobe: remove hardcoded port check in token suffix
- novaprobe: ARGO-948 Access token parameter should be file
* Wed Aug 30 2017 Daniel Vrcic <dvrcic@srce.hr> - 0.1.5-1%{?dist}
- novaprobe: use of ids insteads of urls for flavors and image by Enol Fernandez
- novaprobe: added support for OIDC tokens by Enol Fernandez
* Thu Apr 6 2017 Emir Imamagic <eimamagi@srce.hr> - 0.1.4-1%{?dist}
- Version bump
* Tue Dec 13 2016 Daniel Vrcic <dvrcic@srce.hr> - 0.1.3-1%{?dist}
- refactored keystone token and cert check code
* Tue Nov 22 2016 Emir Imamagic <eimamagi@srce.hr> - 0.1.1-7%{?dist}
- Probes location aligned with guidelines
* Fri May 13 2016 Daniel Vrcic <dvrcic@srce.hr> - 0.1.0-6%{?dist}
- cdmiprobe: add support for printing error msgs from packed exceptions
- cdmiprobe: wait some time before next operation
- cdmiprobe: fetched token implies that we have supported CDMI Specification version
- cdmiprobe: merged improvements with proper cleanup procedure by Enol Fernandez
* Tue Jan 19 2016 Daniel Vrcic <dvrcic@srce.hr> - 0.1.0-5%{?dist}
- remove Py2.6 deprecations in cdmiprobe and novaprobe
* Fri Oct 6 2015 Daniel Vrcic <dvrcic@srce.hr> - 0.1.0-4%{?dist}
- novaprobe: debugging helper leftover removed
* Fri Oct 2 2015 Daniel Vrcic <dvrcic@srce.hr> - 0.1.0-3%{?dist}
- novaprobe: only HTTPS endpoints allowed
* Wed Sep 23 2015 Daniel Vrcic <dvrcic@srce.hr> - 0.1.0-2%{?dist}
- cdmiprobe: handle case when endpoint disabled SSLv3
- novaprobe: added image and flavor cmd options
- novaprobe: no roundtrip, keystone service is given directly
* Fri Sep 18 2015 Emir Imamagic <eimamagi@srce.hr> - 0.1.0-1%{?dist}
- Initial version of EGI FedCloud probes for Nagios
