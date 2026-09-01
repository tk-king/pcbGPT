import React from "react";
import {
  Alert,
  Button,
  FileInput,
  Modal,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertCircle, IconUpload } from "@tabler/icons-react";
import { uploadPart } from "../api/parts.js";

const UploadPartModal = ({ opened, onClose, onUploaded }) => {
  const [kicadSym, setKicadSym] = React.useState(null);
  const [kicadMod, setKicadMod] = React.useState(null);
  const [stepFile, setStepFile] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!opened) {
      setKicadSym(null);
      setKicadMod(null);
      setStepFile(null);
      setLoading(false);
      setError("");
    }
  }, [opened]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!kicadSym || !kicadMod) {
      setError("Upload both the .kicad_sym file and the .kicad_mod file.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const payload = await uploadPart({ kicadSym, kicadMod, stepFile });
      onUploaded?.(payload);
      onClose();
    } catch (nextError) {
      setError(nextError?.message || "Failed to upload part.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create New Part" centered size="lg">
      <form onSubmit={handleSubmit}>
        <Stack gap="md">
          <Text size="sm" c="#607070">
            Upload a KiCad symbol, footprint, and optionally a STEP model. The files will be
            installed into the KiCad library path and re-indexed for part search.
          </Text>

          {error ? (
            <Alert color="red" icon={<IconAlertCircle size={16} />}>
              {error}
            </Alert>
          ) : null}

          <FileInput
            label="KiCad symbol"
            placeholder="Upload .kicad_sym"
            value={kicadSym}
            onChange={setKicadSym}
            accept=".kicad_sym"
            clearable
            required
          />

          <FileInput
            label="KiCad footprint"
            placeholder="Upload .kicad_mod"
            value={kicadMod}
            onChange={setKicadMod}
            accept=".kicad_mod"
            clearable
            required
          />

          <FileInput
            label="STEP model"
            placeholder="Upload .step or .stp (optional)"
            value={stepFile}
            onChange={setStepFile}
            accept=".step,.stp"
            clearable
          />

          <Button type="submit" loading={loading} leftSection={<IconUpload size={16} />}>
            Create Part
          </Button>
        </Stack>
      </form>
    </Modal>
  );
};

export default UploadPartModal;
