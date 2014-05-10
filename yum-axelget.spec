%define build_number 0.4
%define snapshot .20140415
%define source_folder yum-axelget-svn-trunk
Name:           yum-axelget
Version:        1.0
BuildArch:      noarch
Release:        %{build_number}%{?snapshot}%{?dist}
Summary:        Yum plugin to download big files with axel

Group:          System Environment/Base
License:        GPLv2
URL:            https://github.com/crook/yum-axelget
Source0:        https://github.com/crook/yum-axelget/archive/v1.0.4.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

#BuildRequires:
Requires:       axel

%description
Developed by Ray Chen and Wesley Wang from China.
Built by Amos Kong <kongjianjun@gmail.com>.

The latest code can be found in SVN:
https://github.com/crook/yum-axelget


%prep
%setup -q %{?source_folder:-n %{source_folder}}


%build


%install
rm -rf $RPM_BUILD_ROOT
install -m 0755 -d %{buildroot}%{_sysconfdir}/yum/pluginconf.d
install -p -m 0644 axelget.conf %{buildroot}%{_sysconfdir}/yum/pluginconf.d
install -m 0755 -d %{buildroot}%{_libdir}/yum-plugins
install -p -m 0644 axelget.py %{buildroot}%{_libdir}/yum-plugins


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc
%{_libdir}/yum-plugins/axelget.py*
%config(noreplace) %{_sysconfdir}/yum/pluginconf.d/axelget.conf



%changelog
* Sat Apr 05 2014 Ray Chen <chenrano2002@gmail.com> - 1.0-0.4.20140405
- Removed required presto module since it's in yum core code now
- Rewrite drpm download method with new yum presto API

* Sat Jun 17 2013 Amos Kong <kongjianjun@gmail.com> - 1.0-0.3.20130617
- fix for issue 2 on website (chenrano2002)
- modify console output (chenrano2002)
- removed unused module urlparse and fixed some typos (yolkfull)
- move checking plugin procedure as a common function for presto and fastestmirror (yolkfull)

* Sat Jul 05 2008 bbbush <bbbush.yuan@gmail.com> - 1.0-0.2.20080705
- preserve time stamp when copy files
- confirmed that both .pyc and .pyo should be included

* Sat Jul 05 2008 bbbush <bbbush.yuan@gmail.com> - 1.0-0.1.20080705
- create spec

