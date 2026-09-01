import subprocess
import tempfile
import os


def _resolve_kicad_cli() -> str:
    """Return kicad-cli path with env override and PATH fallback."""
    cli = os.getenv("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
    if not os.path.exists(cli):
        cli = "kicad-cli"
    return cli


def kicad_sch_to_netlist(kicad_sch_content) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "input.kicad_sch")
        output_file = os.path.join(temp_dir, "output.net")

        # Write schematic content to input file
        with open(input_file, "w") as f:
            f.write(kicad_sch_content)

        kicad_cli = _resolve_kicad_cli()
        result = subprocess.run(
            [kicad_cli, "sch", "export", "netlist", input_file, "-o", output_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to convert kicad_sch to netlist.\n"
                f"Command: {' '.join(result.args)}\n"
                f"Error: {result.stderr}"
            )

        with open(output_file, "r") as f:
            netlist_content = f.read()

        return netlist_content
    
