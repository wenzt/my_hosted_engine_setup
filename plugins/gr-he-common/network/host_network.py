#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2017 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#


"""
Host network config plugin.
"""

import ethtool
import gettext
import socket
import os
import time

from otopi import plugin
from otopi import util

from vdsm.client import ServerError

from ovirt_setup_lib import hostname as osetuphostname

from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import ansible_utils
from ovirt_hosted_engine_setup import vds_info

def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')

@util.export
class Plugin(plugin.PluginBase):
    """
    host network configuration plugin.
    	1. enable eth VF
    	2. set one eth to mgmt-net
    	3. set one eth to ceph public net
    """

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self._enabled = True
    
    def _init(self):
        self.environment.setdefault(
            ohostedcons.NetworkEnv.VF_IF,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.VF_NM,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.MGMT_NIC_IF,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.MGMT_IPADDR,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.MGMT_NETMASK,
            '255.255.255.0'
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.MGMT_GATEWAY,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.CEPH_NIC_IF,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.CEPH_PUBLIC_IPADDR,
            None
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.CEPH_PUBLIC_NETMASK,
            '255.255.255.0'
        )
        self.environment.setdefault(
            ohostedcons.NetworkEnv.CEPH_PUBLIC_GATEWAY,
            None
        )


    @plugin.event(
        stage = plugin.Stages.STAGE_CUSTOMIZATION,
        name = ohostedcons.Stages.ENABLE_ETHVF,
        priority = plugin.Stages.PRIORITY_FIRST, 
    )
    def _customization(self):
        active_ethName = ethtool.get_active_devices()
        self.environment[
                ohostedcons.NetworkEnv.VF_IF
            ] = self.dialog.queryString(
                name='ovehosted_vf_if',
                note=_(
                    'Please indicate a nic to ebable VF: (@VALUES@): '
                ),
                prompt=True,
                caseSensitive=True,
                validValues=active_ethName,
            )
        self.logger.info(_('indicate nis is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.VF_IF]))

        self.check_indicate_nic_status(self.environment[ohostedcons.NetworkEnv.VF_IF])

        self.environment[
                ohostedcons.NetworkEnv.VF_NM
            ] = self.dialog.queryString(
                name='ovehosted_vf_nm',
                note=_(
                    'Please indicate number of VFs no more than 64: (@VALUES@) [@DEFAULT@]: '
                ),
                prompt=True,
                default='5',
            )

        self.enable_VF(self.environment[ohostedcons.NetworkEnv.VF_IF], self.environment[ohostedcons.NetworkEnv.VF_NM])


    def enable_VF(self, nicName,vfNums):
    	cmd = "echo %s > /sys/class/net/%s/device/sriov_numvfs" % (vfNums, nicName)
        result = os.popen(cmd).read()
    	time.sleep(5)
    	self.logger.info(_('active nics: {nics}').format(nics = ethtool.get_active_devices()))

    def check_indicate_nic_status(self, nicName):
    	path = "/sys/class/net/%s/device/sriov_numvfs" % (nicName)
    	if not os.path.exists(path):
    		raise RuntimeError(_('/sys/class/net/%s/device/sriov_numvfs not exists' % (nicName)))

    	cmd = "cat /sys/class/net/%s/device/sriov_numvfs" % (nicName)
    	result = os.popen(cmd).read()
    	if int(result.strip()):
    	   raise RuntimeError(_('nic VF nums != 0'))

    @plugin.event(
        stage = plugin.Stages.STAGE_CUSTOMIZATION,
        name = ohostedcons.Stages.MGMT_CFG,
        after = (ohostedcons.Stages.ENABLE_ETHVF,),
    )
    def _customization(self):
        active_ethName = ethtool.get_active_devices()
        self.environment[
                ohostedcons.NetworkEnv.MGMT_NIC_IF
            ] = self.dialog.queryString(
                name='ovehosted_mgmt_nic_if',
                note=_(
                    'Please indicate a nic to active Host MGMT network: (@VALUES@): '
                ),
                prompt=True,
                caseSensitive=True,
                validValues=active_ethName,
            )
        self.logger.info(_('indicate nis is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.MGMT_NIC_IF]))

        self.environment[
                ohostedcons.NetworkEnv.MGMT_IPADDR
            ] = self.dialog.queryString(
                name='ovehosted_mgmt_nic_ipaddr',
                note=_(
                    'Please input your Host MGMT network IPADDR: '
                ),
                prompt=True,
                caseSensitive=True,
            )
        self.logger.info(_('ipaddr is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.MGMT_IPADDR]))

        self.environment[
                ohostedcons.NetworkEnv.MGMT_NETMASK
            ] = self.dialog.queryString(
                name='ovehosted_mgmt_nic_netmask',
                note=_(
                    'Please input your Host MGMT network METMASK [@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.NetworkEnv.MGMT_NETMASK,
            )
        self.logger.info(_('netmask is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.MGMT_NETMASK]))

        self.environment[
                ohostedcons.NetworkEnv.MGMT_GATEWAY
            ] = self.dialog.queryString(
                name='ovehosted_mgmt_nic_gateway',
                note=_(
                    'Please input your Host MGMT network GATEWAY: '
                ),
                prompt=True,
                caseSensitive=True,
            )
        self.logger.info(_('gateway is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.MGMT_GATEWAY]))
        eth = self.environment[ohostedcons.NetworkEnv.MGMT_NIC_IF]
        ipaddr = self.environment[ohostedcons.NetworkEnv.MGMT_IPADDR]
        netmask = self.environment[ohostedcons.NetworkEnv.MGMT_NETMASK]
        gateway = self.environment[ohostedcons.NetworkEnv.MGMT_GATEWAY]
        create_mgmt_config_file(eth, ipaddr, netmask, gateway)

    @plugin.event(
        stage = plugin.Stages.STAGE_CUSTOMIZATION,
        name = ohostedcons.Stages.CEPH_PUBLIC_CFG,
        after = (ohostedcons.Stages.MGMT_CFG,),
    )
    def _customization(self):
        active_ethName = ethtool.get_active_devices()
        self.environment[
                ohostedcons.NetworkEnv.CEPH_NIC_IF
            ] = self.dialog.queryString(
                name='ovehosted_ceph_nic_if',
                note=_(
                    'Please indicate a nic to active CEPH Public network: (@VALUES@): '
                ),
                prompt=True,
                caseSensitive=True,
                validValues=active_ethName,
            )
        self.logger.info(_('indicate nis is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.CEPH_NIC_IF]))

        self.environment[
                ohostedcons.NetworkEnv.CEPH_PUBLIC_IPADDR
            ] = self.dialog.queryString(
                name='ovehosted_ceph_public_ipaddr',
                note=_(
                    'Please input your CEPH Public network IPADDR: '
                ),
                prompt=True,
                caseSensitive=True,
            )
        self.logger.info(_('ipaddr is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.CEPH_PUBLIC_IPADDR]))

        self.environment[
                ohostedcons.NetworkEnv.CEPH_PUBLIC_NETMASK
            ] = self.dialog.queryString(
                name='ovehosted_ceph_public_netmask',
                note=_(
                    'Please input your CEPH Public network METMASK [@DEFAULT@]: '
                ),
                prompt=True,
                caseSensitive=True,
                default=ohostedcons.NetworkEnv.CEPH_PUBLIC_NETMASK,
            )
        self.logger.info(_('netmask is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.CEPH_PUBLIC_NETMASK]))

        self.environment[
                ohostedcons.NetworkEnv.CEPH_PUBLIC_GATEWAY
            ] = self.dialog.queryString(
                name='ovehosted_ceph_public_gateway',
                note=_(
                    'Please input your CEPH Public network GATEWAY: '
                ),
                prompt=True,
                caseSensitive=True,
            )
        self.logger.info(_('gateway is {eth}').format(eth = self.environment[ohostedcons.NetworkEnv.CEPH_PUBLIC_GATEWAY]))
        
        eth = self.environment[ohostedcons.NetworkEnv.CEPH_NIC_IF]
        ipaddr = self.environment[ohostedcons.NetworkEnv.CEPH_PUBLIC_IPADDR]
        netmask = self.environment[ohostedcons.NetworkEnv.CEPH_PUBLIC_NETMASK]
        gateway = self.environment[ohostedcons.NetworkEnv.CEPH_PUBLIC_GATEWAY]
        create_mgmt_config_file(eth, ipaddr, netmask, gateway)




    def create_mgmt_config_file(self, eth, ipaddr, netmask, gateway):
        # better way ?
        path = "/etc/sysconfig/network-scripts/ifcfg-%s" % (eth)
        with open(path, 'w') as file:
            file.write("TYPE=Ethernet\n")
            file.write("BOOTPROTO=static\n")
            file.write("DEFROUTE=yes\n")
            file.write("IPV4_FAILURE_FATAL=no\n")
            file.write("NAME=%s\n" % (eth))
            file.write("DEVICE=%s\n" % (eth))
            file.write("ONBOOT=yes\n")
            file.write("IPADDR=%s\n" % (ipaddr))
            file.write("NETMASK=%s\n" % (netmask))
            if gateway:
                file.write("GATEWAY=%s\n" % (gateway))
        cmd = "systemctl restart network"
        os.popen(cmd) #need stderr
        time.sleep(5) 
        check_mgmt_pingable(ipaddr)

    def check_mgmt_pingable(self, ipaddr):
        cmd = "ping -c3 %s" % (ipaddr)
        result = os.popen(cmd).readlines()
        for line in result:
            if "Unreachable" in line:
                raise RuntimeError(_('nic mgmt set failed!!!!!!!!!'))



