PKGNAME=argo-probe-fedcloud
SPECFILE=${PKGNAME}.spec
FILES=Makefile ${SPECFILE} src

PKGVERSION=$(shell grep -s '^Version:' $(SPECFILE) | sed -e 's/Version: *//')

dist:
	rm -rf dist
	python3 setup.py sdist
	mv dist/${PKGNAME}-${PKGVERSION}.tar.gz .
	rm -rf dist

rpmdirs:
	mkdir -p {BUILD,RPMS,SOURCES,SPECS,SRPMS}

srpm: dist rpmdirs
	rpmbuild -ts --define "_topdir $(CURDIR)" ${PKGNAME}-${PKGVERSION}.tar.gz

rpm: dist rpmdirs
	rpmbuild -ta --define "_topdir $(CURDIR)" ${PKGNAME}-${PKGVERSION}.tar.gz

sources: dist

clean:
	rm -rf ${PKGNAME}-${PKGVERSION}.tar.gz
	rm -f MANIFEST
	rm -rf dist
	rm -rf {BUILD,RPMS,SOURCES,SPECS,SRPMS}
