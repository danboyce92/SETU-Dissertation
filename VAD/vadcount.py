#Example
# vol -f "C:\Users\duff1\Desktop\VADWork\Run001.vmem" -p "C:\Users\duff1\Documents\Volatility3\custom_plugins" -r csv windows.vadcount.VadCountCheck > "C:\Users\duff1\Desktop\VADWork\raw_vadcount.csv"

from volatility3.framework import interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.plugins.windows import pslist


class VadCountCheck(interfaces.plugins.PluginInterface):
    _required_framework_version = (2, 0, 0)

    @classmethod
    # Required for volatility plugins
    def get_requirements(cls):
        return [
            requirements.ModuleRequirement(
                name="kernel",
                description="Windows kernel",
                architectures=["Intel32", "Intel64"],
            ),
            requirements.VersionRequirement(
                name="pslist", component=pslist.PsList, version=(3, 0, 0)
            ),
        ]

    # Loop through each process and get a vad node count
    def _generator(self, procs):
        for proc in procs:
            pid = proc.UniqueProcessId
            name = proc.ImageFileName.cast(
                "string", max_length=proc.ImageFileName.vol.count, errors="replace"
            )

            vad_count = 0
            error = ""
            try:
                for _ in proc.get_vad_root().traverse():
                    vad_count += 1
            except Exception as exc:
                vad_count = -1
                error = str(exc)

            yield (0, (pid, name, vad_count, error))

    def run(self):
        procs = pslist.PsList.list_processes(
            context=self.context,
            kernel_module_name=self.config["kernel"],
        )

        return renderers.TreeGrid(
            [
                ("PID", int),
                ("Process", str),
                ("VadNodeCount", int),
                ("Error", str),
            ],
            self._generator(procs),
        )
