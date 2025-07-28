Summary:       ARGO probes for EGI FedCloud services
Name:          argo-probe-fedcloud
Version:       0.11.2
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
