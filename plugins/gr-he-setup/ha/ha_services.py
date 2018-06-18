#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013-2015 Red Hat, Inc.
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
HA services
"""


import gettext
import os

from otopi import plugin
from otopi import util

from ovirt_hosted_engine_setup import constants as ohostedcons


def _(m):
    return gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    HA services plugin.
    """

    SHUTDOWN_DELAY_SECS = '10'

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)

    @plugin.event(
        stage=plugin.Stages.STAGE_PROGRAMS,
    )
    def _programs(self):
        for service in (
            ohostedcons.Const.HA_AGENT_SERVICE,
            ohostedcons.Const.HA_BROCKER_SERVICE,
        ):
            if self.services.status(
                name=service,
            ):
                if os.path.exists(ohostedcons.FileLocations.ENGINE_VM_CONF):
                    raise RuntimeError(
                        _(
                            'Hosted Engine HA services are already running '
                            'on this system. Hosted Engine cannot be '
                            'deployed on a host already running those '
                            'services.'
                        )
                    )
                else:
                    # Services are running by accident:
                    # stopping them and continue the setup.
                    # Related-To: https://bugzilla.redhat.com/1134873
                    for service in (
                        ohostedcons.Const.HA_AGENT_SERVICE,
                        ohostedcons.Const.HA_BROCKER_SERVICE,
                    ):
                        self.services.state(
                            name=service,
                            state=False,
                        )

    @plugin.event(
        stage=plugin.Stages.STAGE_CLOSEUP,
        after=(
            ohostedcons.Stages.VM_SHUTDOWN,
        ),
        name=ohostedcons.Stages.HA_START,
    )
    def _closeup(self):
        self.logger.info(_('Enabling and starting HA services'))
        for service in (
            ohostedcons.Const.HA_AGENT_SERVICE,
            ohostedcons.Const.HA_BROCKER_SERVICE,
        ):
            self.services.startup(
                name=service,
                state=True,
            )
            self.services.state(
                name=service,
                state=True,
            )


# vim: expandtab tabstop=4 shiftwidth=4
