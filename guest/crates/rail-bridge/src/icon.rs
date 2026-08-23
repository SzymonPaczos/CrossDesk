//! Extracts a window's application icon at high resolution and PNG-encodes
//! it for the `RailWindowEvent.icon_png` field.
//!
//! Why the process `.exe` and not the live window icon: the window icon
//! Windows exposes over a RAIL ICON order (and via `WM_GETICON`) is capped
//! at the small/large system icon size (typically 16–32 px), so FreeRDP's
//! native `_NET_WM_ICON` ends up blurry in docks / hi-DPI. The executable's
//! icon-group resource carries the full 256×256 variant for modern apps, so
//! we extract *that* (`PrivateExtractIconsW` at 256) and let the host set a
//! crisp multi-size `_NET_WM_ICON`.
//!
//! The pixel-munging + PNG helpers are platform-independent (and unit-tested
//! on any host); the icon *extraction* is `#[cfg(windows)]` because it is all
//! Win32. `extract_window_icon_png` is only reachable from the Windows-only
//! `events` module.

// The pixel helpers are only compiled where they're used — the Windows
// extraction path and the (cross-platform) unit tests — so a plain Linux
// `cargo check` doesn't flag them as dead code under the workspace's
// deny-warnings lint.

/// In-place BGRA→RGBA swap. If every alpha byte is zero (older icons that
/// store transparency only in the AND mask, not the color bitmap), force the
/// image opaque so it doesn't render fully transparent — a visible icon beats
/// an invisible one, and the mask-precise path is a later refinement.
#[cfg(any(windows, test))]
fn bgra_to_rgba_in_place(buf: &mut [u8]) {
    let any_alpha = buf.as_chunks::<4>().0.iter().any(|px| px[3] != 0);
    for px in buf.as_chunks_mut::<4>().0 {
        px.swap(0, 2); // B <-> R
        if !any_alpha {
            px[3] = 0xff;
        }
    }
}

/// PNG-encode top-down RGBA8 pixels.
#[cfg(any(windows, test))]
fn encode_png(width: u32, height: u32, rgba: &[u8]) -> Option<Vec<u8>> {
    let mut out: Vec<u8> = Vec::new();
    {
        let mut enc = png::Encoder::new(&mut out, width, height);
        enc.set_color(png::ColorType::Rgba);
        enc.set_depth(png::BitDepth::Eight);
        let mut writer = enc.write_header().ok()?;
        writer.write_image_data(rgba).ok()?;
    }
    Some(out)
}

#[cfg(windows)]
pub use win::extract_window_icon_png;

#[cfg(windows)]
mod win {
    use super::{bgra_to_rgba_in_place, encode_png};
    use tracing::{debug, info};
    use windows::core::PWSTR;
    use windows::Win32::Foundation::{CloseHandle, HANDLE, HWND};
    use windows::Win32::Graphics::Gdi::{
        DeleteObject, GetDC, GetDIBits, GetObjectW, ReleaseDC, BITMAP, BITMAPINFO,
        BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, HBITMAP,
    };
    use windows::Win32::System::Threading::{
        OpenProcess, QueryFullProcessImageNameW, PROCESS_NAME_WIN32,
        PROCESS_QUERY_LIMITED_INFORMATION,
    };
    use windows::Win32::UI::WindowsAndMessaging::{
        DestroyIcon, GetIconInfo, GetWindowThreadProcessId, PrivateExtractIconsW, HICON, ICONINFO,
    };

    /// Requested icon edge in pixels. Modern executables carry a 256×256 PNG
    /// variant in their icon group; `PrivateExtractIconsW` returns the best
    /// match scaled to this size.
    const ICON_EDGE: i32 = 256;

    /// Extract the PNG-encoded application icon for the process that owns
    /// *hwnd*, or `None` when no icon is available (system windows with no
    /// associated executable icon, access-denied processes, extraction/encode
    /// failure). Never panics — icon extraction is best-effort decoration.
    pub fn extract_window_icon_png(hwnd: HWND) -> Option<Vec<u8>> {
        let exe = process_image_path(hwnd)?;
        let hicon = extract_largest_icon(&exe)?;
        let rgba = hicon_to_rgba(hicon);
        // Safety: `hicon` was handed to us by PrivateExtractIconsW; we own it
        // and destroy it exactly once here regardless of the conversion result.
        unsafe {
            let _ = DestroyIcon(hicon);
        }
        let (w, h, pixels) = rgba?;
        let png = encode_png(w, h, &pixels)?;
        info!(bytes = png.len(), w, h, exe = %exe, "extracted window icon");
        // Optional debug dump: when CROSSDESK_ICON_DUMP_DIR is set, write the
        // PNG there so the icon can be eyeballed off-box during bring-up.
        if let Some(dir) = std::env::var_os("CROSSDESK_ICON_DUMP_DIR") {
            let path = std::path::Path::new(&dir).join(format!("icon-{}.png", w));
            if let Err(e) = std::fs::write(&path, &png) {
                debug!("icon dump to {path:?} failed: {e}");
            }
        }
        Some(png)
    }

    /// Resolve the full filesystem path of the executable backing *hwnd*'s
    /// process. Uses `PROCESS_QUERY_LIMITED_INFORMATION`, which a non-elevated
    /// session can open for processes it owns.
    fn process_image_path(hwnd: HWND) -> Option<String> {
        let mut pid = 0u32;
        // Safety: callback-supplied hwnd is valid here; &mut pid is unique.
        unsafe {
            GetWindowThreadProcessId(hwnd, Some(&mut pid));
        }
        if pid == 0 {
            return None;
        }

        // Safety: standard OpenProcess; the returned HANDLE is closed below.
        let handle: HANDLE =
            unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid) }.ok()?;

        let mut buf = vec![0u16; 1024];
        let mut size = buf.len() as u32;
        // Safety: handle is live; buf/size are the documented out-buffer pair;
        // PROCESS_NAME_WIN32 requests a drive-letter path.
        let result = unsafe {
            QueryFullProcessImageNameW(
                handle,
                PROCESS_NAME_WIN32,
                PWSTR(buf.as_mut_ptr()),
                &mut size,
            )
        };
        // Safety: handle is owned by us and unused after this point.
        unsafe {
            let _ = CloseHandle(handle);
        }
        result.ok()?;
        Some(String::from_utf16_lossy(&buf[..size as usize]))
    }

    /// Extract the largest icon (at [`ICON_EDGE`]) from *exe_path*'s group.
    fn extract_largest_icon(exe_path: &str) -> Option<HICON> {
        // windows-rs models szfilename as a fixed `&[u16; 260]` (MAX_PATH);
        // zero-pad so it is NUL-terminated. Paths longer than MAX_PATH are out
        // of scope for icon decoration.
        let wide: Vec<u16> = exe_path.encode_utf16().collect();
        if wide.len() >= 260 {
            return None;
        }
        let mut name = [0u16; 260];
        name[..wide.len()].copy_from_slice(&wide);

        // The slice length (1) is how windows-rs conveys nicons.
        let mut icons = [HICON::default(); 1];
        // Safety: `name` is a fixed [u16;260] NUL-padded buffer; `icons` is a
        // 1-slot slice the call fills with at most one HICON we then own.
        let extracted = unsafe {
            PrivateExtractIconsW(&name, 0, ICON_EDGE, ICON_EDGE, Some(&mut icons[..]), None, 0)
        };
        if extracted == 0 || icons[0].is_invalid() {
            return None;
        }
        Some(icons[0])
    }

    /// Convert an `HICON` to top-down RGBA8 pixels via its 32-bpp color
    /// bitmap. Returns `(width, height, rgba)`.
    fn hicon_to_rgba(hicon: HICON) -> Option<(u32, u32, Vec<u8>)> {
        let mut info = ICONINFO::default();
        // Safety: hicon is valid; &mut info is a unique out-param. On success
        // it hands us two GDI bitmaps we must delete.
        unsafe { GetIconInfo(hicon, &mut info) }.ok()?;
        let color = info.hbmColor;
        let mask = info.hbmMask;

        let result = color_bitmap_to_rgba(color);

        // Safety: both bitmaps were created by GetIconInfo for us; delete each
        // once. HBITMAP converts into the HGDIOBJ the call expects.
        unsafe {
            if !color.is_invalid() {
                let _ = DeleteObject(color);
            }
            if !mask.is_invalid() {
                let _ = DeleteObject(mask);
            }
        }
        result
    }

    fn color_bitmap_to_rgba(color: HBITMAP) -> Option<(u32, u32, Vec<u8>)> {
        if color.is_invalid() {
            return None;
        }
        let mut bm = BITMAP::default();
        // Safety: color is a valid HBITMAP (converts into HGDIOBJ); GetObjectW
        // fills `bm` with its header (sized exactly).
        let got = unsafe {
            GetObjectW(
                color,
                std::mem::size_of::<BITMAP>() as i32,
                Some(std::ptr::addr_of_mut!(bm).cast()),
            )
        };
        if got == 0 || bm.bmWidth <= 0 || bm.bmHeight <= 0 {
            return None;
        }
        let width = bm.bmWidth as u32;
        let height = bm.bmHeight as u32;

        // Negative biHeight = top-down rows (PNG order). 32 bpp BI_RGB gives
        // BGRA with the icon's real alpha channel for modern 32-bit icons.
        let mut bi = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: bm.bmWidth,
                biHeight: -bm.bmHeight,
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };

        let mut buf = vec![0u8; (width * height * 4) as usize];
        // Safety: GetDC(NULL HWND) returns the screen DC; GetDIBits writes at
        // most width*height*4 bytes into `buf` (sized exactly) for `height`
        // scanlines; `bi` describes that layout. ReleaseDC pairs the GetDC.
        let scanlines = unsafe {
            let hdc = GetDC(HWND::default());
            let n = GetDIBits(
                hdc,
                color,
                0,
                height,
                Some(buf.as_mut_ptr().cast()),
                std::ptr::addr_of_mut!(bi).cast(),
                DIB_RGB_COLORS,
            );
            ReleaseDC(HWND::default(), hdc);
            n
        };
        if scanlines == 0 {
            return None;
        }

        bgra_to_rgba_in_place(&mut buf);
        Some((width, height, buf))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bgra_to_rgba_swaps_channels_and_keeps_alpha() {
        // One pixel: B=1 G=2 R=3 A=4 → R=3 G=2 B=1 A=4 (alpha preserved
        // because at least one pixel has non-zero alpha).
        let mut buf = vec![1u8, 2, 3, 4];
        bgra_to_rgba_in_place(&mut buf);
        assert_eq!(buf, vec![3, 2, 1, 4]);
    }

    #[test]
    fn bgra_to_rgba_forces_opaque_when_all_alpha_zero() {
        // Two pixels, both alpha 0 → channels swap AND alpha forced opaque.
        let mut buf = vec![10u8, 20, 30, 0, 40, 50, 60, 0];
        bgra_to_rgba_in_place(&mut buf);
        assert_eq!(buf, vec![30, 20, 10, 0xff, 60, 50, 40, 0xff]);
    }

    #[test]
    fn encode_png_produces_a_valid_signature() {
        // 1×1 opaque red, RGBA. The 8-byte PNG signature must lead the output.
        let png = encode_png(1, 1, &[255, 0, 0, 255]).expect("encode");
        assert_eq!(&png[..8], b"\x89PNG\r\n\x1a\n");
    }
}
