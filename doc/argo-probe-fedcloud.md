# ARGO probe for EGI FedCloud services

This package includes probes for EGI FedCloud services. Currently, it supports
the following tests:

- [OpenStack Nova](#openstack-nova-novaprobe)
- [OpenStack Swift](#openstack-swift-swiftprobe)
- [FedCloud Accounting Freshness](#fedcloud-accounting-freshness-check_fedcloud_accnt)

## OpenStack Nova (`novaprobe`)

`eu.egi.cloud.OpenStack-VM` Nagios test uses `novaprobe` to:

- Discover the image identifier of the EGI monitoring image
- Discover the smallest flavour that fits the image
- Discover available networks
- Create a VM with the discovered image, flavour and network
- Wait for the VM to become active
- Destroy the VM

In order for the probe to work properly, sites need to provide Keystone URL in
the GOCDB URL. Command executed is:

```shell
novaprobe --endpoint $KEYSTONE_ENDPOINT --appdb-image 1017
```

## OpenStack Swift (`swiftprobe`)

`eu.egi.cloud.OpenStack-Swift` Nagios test uses `swiftprobe` probe to:

- Establish a connection with the OpenStack Swift Object Storage
- Create a new Open Stack Swift Container
- Create a new object file
- Fetch the object file
- Delete the object file
- Delete the OpenStack Swift Container
- Close connection with the OpenStack Swift Object Storage

In order for the probe to work properly, sites need to provide Keystone URL in
the GOCDB URL. Probe uses OIDC token.

```shell
swiftprobe.py --endpoint $KEYSTONE_ENDPOINT --access-token $OIDC_ACCESS_TOKEN
```

## FedCloud Accounting Freshness (`check_fedcloud_accnt`)

Check looks at the
[Accounting report](http://goc-accounting.grid-support.ac.uk/cloudtest/cloudsites2.html)
and checks if the GOCDB entry is there. It also checks `lastupdate` field and
raise:

- `WARNING`: if `lastupdate` is older than 7 days
- `CRITICAL`: if `lastupdate` is older than 30 days

When searching the accounting report, the probe uses the name provided in the
URL in the GOCDB entry.
