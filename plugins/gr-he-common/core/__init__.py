#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2016-2017 Red Hat, Inc.
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


"""hosted engine common plugin."""

from otopi import util

from . import answerfile
from . import ha_notifications
from . import misc
from . import remote_answerfile
from . import shell
from . import titles
from . import vdsmconf


@util.export
def createPlugins(context):
    answerfile.Plugin(context=context)
    ha_notifications.Plugin(context=context)
    misc.Plugin(context=context)
    remote_answerfile.Plugin(context=context)
    vdsmconf.Plugin(context=context)
    titles.Plugin(context=context)
    shell.Plugin(context=context)


# vim: expandtab tabstop=4 shiftwidth=4
