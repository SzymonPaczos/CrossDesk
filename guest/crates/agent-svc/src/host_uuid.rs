//! Reads the libvirt domain UUID stamped by the host into SMBIOS Type 1.
//!
//! libvirt's `<sysinfo type='smbios'>` element copies the domain UUID into the
//! SMBIOS System Information block, which the guest can read via
//! `GetSystemFirmwareTable('RSMB', …)`. Sending this value back to the host in
//! `ClientHello` lets the host cross-check that it is talking to the VM it
//! booted, not some other process holding a vsock CID.

const ENV_OVERRIDE: &str = "CROSSDESK_DOMAIN_UUID";

pub fn read_host_domain_uuid() -> anyhow::Result<String> {
    if let Ok(env) = std::env::var(ENV_OVERRIDE) {
        return Ok(env);
    }

    #[cfg(windows)]
    {
        smbios::read()
    }
    #[cfg(not(windows))]
    {
        anyhow::bail!(
            "SMBIOS UUID can only be read on Windows; set {ENV_OVERRIDE} for non-Windows targets"
        )
    }
}

#[cfg(windows)]
mod smbios {
    use windows::Win32::System::SystemInformation::GetSystemFirmwareTable;

    // 'RSMB' little-endian, as the Win32 API expects.
    const SMBIOS_PROVIDER: u32 = u32::from_le_bytes(*b"RSMB");
    const RAW_SMBIOS_HEADER_LEN: usize = 8;
    const TYPE_SYSTEM_INFORMATION: u8 = 1;
    const TYPE_END_OF_TABLE: u8 = 127;
    const UUID_OFFSET_IN_SYSINFO: usize = 8;
    const UUID_LEN: usize = 16;

    pub fn read() -> anyhow::Result<String> {
        let raw = read_smbios_table()?;
        let table = raw
            .get(RAW_SMBIOS_HEADER_LEN..)
            .ok_or_else(|| anyhow::anyhow!("SMBIOS buffer shorter than RawSMBIOSData header"))?;

        let uuid_bytes = find_system_info_uuid(table)?;
        Ok(format_smbios_uuid(uuid_bytes))
    }

    fn read_smbios_table() -> anyhow::Result<Vec<u8>> {
        // Two-call idiom: first probe with a zero buffer to get the size, then
        // allocate and fill.
        let size = unsafe { GetSystemFirmwareTable(SMBIOS_PROVIDER, 0, None) };
        if size == 0 {
            anyhow::bail!("GetSystemFirmwareTable returned 0 (SMBIOS unavailable)");
        }

        let mut buf = vec![0u8; size as usize];
        let written = unsafe { GetSystemFirmwareTable(SMBIOS_PROVIDER, 0, Some(&mut buf)) };
        if written == 0 || written as usize > buf.len() {
            anyhow::bail!(
                "GetSystemFirmwareTable copy returned {written} into a {size}-byte buffer"
            );
        }
        buf.truncate(written as usize);
        Ok(buf)
    }

    fn find_system_info_uuid(table: &[u8]) -> anyhow::Result<&[u8]> {
        let mut i = 0;
        while i + 4 <= table.len() {
            let stype = table[i];
            let slen = table[i + 1] as usize;
            if slen < 4 || i + slen > table.len() {
                anyhow::bail!("Malformed SMBIOS structure at offset {i}");
            }

            if stype == TYPE_SYSTEM_INFORMATION {
                let start = i + UUID_OFFSET_IN_SYSINFO;
                let end = start + UUID_LEN;
                if end > i + slen {
                    anyhow::bail!("System Information struct too short to hold UUID");
                }
                return Ok(&table[start..end]);
            }

            if stype == TYPE_END_OF_TABLE {
                break;
            }

            // After the formatted area come strings, terminated by a double NUL.
            let mut j = i + slen;
            let mut terminated = false;
            while j + 1 < table.len() {
                if table[j] == 0 && table[j + 1] == 0 {
                    j += 2;
                    terminated = true;
                    break;
                }
                j += 1;
            }
            if !terminated {
                anyhow::bail!("Unterminated SMBIOS string area at offset {i}");
            }
            i = j;
        }

        anyhow::bail!("SMBIOS Type 1 (System Information) not found")
    }

    fn format_smbios_uuid(b: &[u8]) -> String {
        // SMBIOS 2.6+: the first three fields (time_low, time_mid, time_hi_and_version)
        // are stored little-endian; the remaining clock_seq + node bytes are big-endian.
        format!(
            "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
            b[3], b[2], b[1], b[0],
            b[5], b[4],
            b[7], b[6],
            b[8], b[9],
            b[10], b[11], b[12], b[13], b[14], b[15],
        )
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn formats_smbios_uuid_with_le_first_three_fields() {
            // SMBIOS-on-the-wire bytes for canonical UUID
            // 11223344-5566-7788-99aa-bbccddeeff00:
            let bytes = [
                0x44, 0x33, 0x22, 0x11, // time_low (LE)
                0x66, 0x55,             // time_mid (LE)
                0x88, 0x77,             // time_hi_and_version (LE)
                0x99, 0xaa,             // clock_seq (BE)
                0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x00, // node (BE)
            ];
            assert_eq!(
                format_smbios_uuid(&bytes),
                "11223344-5566-7788-99aa-bbccddeeff00"
            );
        }

        #[test]
        fn finds_uuid_in_minimal_table() {
            let mut table = vec![1u8, 27]; // Type=1, Length=27
            table.extend_from_slice(&[0, 0]); // Handle
            table.extend_from_slice(&[0, 0, 0, 0]); // Manufacturer..Serial string indices
            table.extend_from_slice(&[
                0x44, 0x33, 0x22, 0x11, 0x66, 0x55, 0x88, 0x77, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee,
                0xff, 0x00,
            ]);
            table.extend_from_slice(&[0, 0, 0]); // Wake-up Type, SKU idx, Family idx
            table.extend_from_slice(&[0, 0]); // empty string area terminator

            let uuid = find_system_info_uuid(&table).expect("uuid present");
            assert_eq!(format_smbios_uuid(uuid), "11223344-5566-7788-99aa-bbccddeeff00");
        }
    }
}
