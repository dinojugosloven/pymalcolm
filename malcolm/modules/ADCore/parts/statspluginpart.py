import os
from xml.etree import cElementTree as ET

from malcolm.compat import et_to_string
from malcolm.core import REQUIRED, method_takes
from malcolm.modules.ADCore.infos import CalculatedNDAttributeDatasetInfo
from malcolm.modules.builtin.parts import StatefulChildPart
from malcolm.modules.builtin.vmetas import StringMeta
from malcolm.modules.scanning.controllers import RunnableController


class StatsPluginPart(StatefulChildPart):
    """Stats plugin"""
    # The NDAttributes file we write to say what to capture
    attributes_filename = None

    @RunnableController.ReportStatus
    def report_info(self, _):
        return [CalculatedNDAttributeDatasetInfo(name="sum", attr="StatsTotal")]

    def _make_attributes_xml(self):
        # Make a root element with an NXEntry
        root_el = ET.Element("Attributes")
        ET.SubElement(
            root_el, "Attribute", addr="0", datatype="DOUBLE", type="PARAM",
            description="Sum of the array", name="StatsTotal", source="TOTAL",
        )
        xml = et_to_string(root_el)
        return xml

    @RunnableController.Configure
    @method_takes(
        "fileDir", StringMeta("File directory to write data to"), REQUIRED)
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        child = context.block_view(self.params.mri)
        fs = child.put_attribute_values_async(dict(
            enableCallbacks=True,
            computeStatistics=True))
        xml = self._make_attributes_xml()
        self.attributes_filename = os.path.join(
            params.fileDir, "%s-attributes.xml" % self.params.mri)
        open(self.attributes_filename, "w").write(xml)
        fs.append(
            child.attributesFile.put_value_async(self.attributes_filename))
        context.wait_all_futures(fs)

    @RunnableController.PostRunIdle
    def post_run_idle(self, context):
        # Delete the attribute XML file
        os.remove(self.attributes_filename)
