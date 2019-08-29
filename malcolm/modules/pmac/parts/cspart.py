from annotypes import add_call_types, Anno

from malcolm.core import DEFAULT_TIMEOUT, PartRegistrar
from malcolm.modules import builtin, scanning
from ..util import CS_AXIS_NAMES
from ..infos import PmacCsKinematicsInfo


with Anno("Co-ordinate system number"):
    ACS = int
with Anno("Motor position to move to in EGUs"):
    ADemandPosition = float
with Anno("Time to take to perform move in seconds"):
    AMoveTime = float

# Pull re-used annotypes into our namespace in case we are subclassed
AMri = builtin.parts.AMri


class CSPart(builtin.parts.ChildPart):
    def __init__(self, mri, cs):
        # type: (AMri, ACS) -> None
        super(CSPart, self).__init__("CS%d" % cs, mri, initial_visibility=True)
        self.cs = cs

    def setup(self, registrar):
        # type: (PartRegistrar) -> None
        super(CSPart, self).setup(registrar)
        # Add methods
        registrar.add_method_model(
            self.move, "moveCS%d" % self.cs, needs_context=True)
        # Hooks
        registrar.hook(scanning.hooks.ReportStatusHook, self.report_status)

    @add_call_types
    def report_status(self, context):
        # type: (scanning.hooks.AContext) -> scanning.hooks.UInfos
        child = context.block_view(self.mri)
        info = PmacCsKinematicsInfo(
            child.port,
            child.qVariables.value,
            child.forward.value,
            child.inverse.value
        )
        return info

    @add_call_types
    def init(self, context):
        # type: (builtin.hooks.AContext) -> None
        super(CSPart, self).init(context)
        # Check the port name matches our CS number
        child = context.block_view(self.mri)
        cs_port = child.port.value
        assert cs_port.endswith(str(self.cs)), \
            "CS Port %s doesn't end with port number %d" % (cs_port, self.cs)

    # Serialize, so use camelCase
    # noinspection PyPep8Naming
    @add_call_types
    def move(self,
             context,  # type: builtin.hooks.AContext
             a=None,  # type: ADemandPosition
             b=None,  # type: ADemandPosition
             c=None,  # type: ADemandPosition
             u=None,  # type: ADemandPosition
             v=None,  # type: ADemandPosition
             w=None,  # type: ADemandPosition
             x=None,  # type: ADemandPosition
             y=None,  # type: ADemandPosition
             z=None,  # type: ADemandPosition
             moveTime=0  # type: AMoveTime
             ):
        # type: (...) -> None
        """Move the given CS axes using a deferred co-ordinated move"""
        child = context.block_view(self.mri)
        child.deferMoves.put_value(True)
        # Convert move time into milliseconds
        child.csMoveTime.put_value(moveTime*1000.0)
        # Add in the motors we need to move
        attribute_values = {}
        for axis in CS_AXIS_NAMES:
            demand = locals()[axis.lower()]
            if demand is not None:
                attribute_values["demand%s" % axis] = demand
        fs = child.put_attribute_values_async(attribute_values)
        # Wait for the demand to have been received by the PV
        for attr, value in sorted(attribute_values.items()):
            child.when_value_matches(attr, value, timeout=1.0)
        # Start the move
        child.deferMoves.put_value(False)
        # Wait for them to get there
        context.wait_all_futures(
            fs, timeout=moveTime + DEFAULT_TIMEOUT)

#    def inverse_kinematics():
#    def forward_kinematics():
