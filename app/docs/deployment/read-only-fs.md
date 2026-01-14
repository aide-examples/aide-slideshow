# Read-Only Filesystem (Power Loss Protection)

Protecting SD card from corruption during power loss.

**This setup is optional.** The slideshow works perfectly fine without it - simply clone the repository and run. The read-only configuration is only recommended for long-term unattended operation where the Pi may lose power unexpectedly.

## Concept

```
SD Card Layout:
┌─────────────────────────────────────────────────────┐
│ Partition 1: /boot/firmware (FAT32, ~512MB)         │
├─────────────────────────────────────────────────────┤
│ Partition 2: / (ext4, ~4-8GB) → READ-ONLY           │
│   - System, Python                                  │
├─────────────────────────────────────────────────────┤
│ Partition 3: /data (ext4, remaining) → READ-WRITE   │
│   - Images: /home/pi/img → /data/img                │
│   - App code: /home/pi/app → /data/app              │
│   - Framework: /home/pi/aide-frame → /data/aide-frame│
└─────────────────────────────────────────────────────┘
```

**Advantage:** The slideshow uses relative paths. Symlinks make the transition transparent - no code changes required. The `app` symlink also enables remote updates on a read-only root filesystem.

## Setup

### 1. Create Backup (Windows)

Use **Win32 Disk Imager** (https://win32diskimager.org):

1. Insert SD card into Windows PC
2. Open Win32 Disk Imager
3. Select a path for the backup file (e.g., `D:\backup\slideshow.img`)
4. Select the SD card drive letter
5. Click **Read** to create the backup image

To restore later: Select the `.img` file and click **Write**.

### 2. Partition SD Card

**Prerequisites:** A USB stick with Raspbian OS 32 Lite.

We want to shrink the system partition on the SD card. This can only be done if the raspi is booted from a different storage device. Prepare a USB stick with OS 32 Lite and boot from there (with the SD card removed). Insert the SD card. Use e2fsck, then resize2fs and fdisk. Be careful.
```
sudo e2fsck -f /dev/mmcblk0p2
sudo resize2fs /dev/mmcblk0p2 8G
```
The next step should be done on the target hardware, although
the fdisk command will warn you. When we did this step on the
other raspi where we had executed the resize2fs command the
altered partition table was not correctly recognized later on the target hardware.

'''
sudo fdisk /dev/mmcblk0
    p (remember start),d 2,
    n p 2, start, +8G, do not remove signature,
    p (remember end), n,p,3, start = end+1, enter,p,
    w or q
sudo mkfs.ext4 /dev/mmcblk0p3
lsblk
```

### 3. Configure New Partition (on the Pi)

Insert SD card into Pi and boot:

```bash
# Create mount point
sudo mkdir -p /data

# Add to /etc/fstab
echo '/dev/mmcblk0p3  /data  ext4  defaults,noatime  0  2' | sudo tee -a /etc/fstab

# Mount
sudo mount /data

# Set permissions
sudo chown pi:pi /data
```

### 4. Move Data and Create Symlinks

Assuming your slideshow is installed directly under `/home/pi/` with `app/`, `img/`, and `aide-frame/` directories:

```bash
# Move images to new partition
sudo mv /home/pi/img /data/img

# Move app code to new partition (for remote updates)
sudo mv /home/pi/app /data/app

# Move aide-frame to new partition
sudo mv /home/pi/aide-frame /data/aide-frame

# Create symlinks
ln -s /data/img /home/pi/img
ln -s /data/app /home/pi/app
ln -s /data/aide-frame /home/pi/aide-frame

# Create update state directory
mkdir -p /data/.update/{backup,staging}
ln -s /data/.update /home/pi/.update

# Set permissions
sudo chown -R pi:pi /data

# Verify
ls -la /home/pi/img         # Should point to /data/img
ls -la /home/pi/app         # Should point to /data/app
ls -la /home/pi/aide-frame  # Should point to /data/aide-frame
```

**Important:** The `aide-frame` directory contains the framework used by the slideshow. It must be a sibling of `app/` (i.e., at `/home/pi/aide-frame/`) because `slideshow.py` looks for it at `../aide-frame/python/` relative to `app/`.

### 5. Enable Read-Only Filesystem via raspi-config

Use the built-in Raspberry Pi OS overlay filesystem feature:

```bash
sudo raspi-config
```

Navigate to: **Performance Options → Overlay File System**

1. Select **Yes** to enable the overlay filesystem
2. Select **Yes** to write-protect the boot partition
3. Reboot when prompted

After reboot, the root filesystem is write-protected using overlayfs. All write operations go to RAM and are lost after reboot - except on `/data` which remains writable.

**Check status:**
```bash
# Check if overlay is active (0 = enabled)
sudo raspi-config nonint get_overlay_now

# Check if overlay is configured for next boot
sudo raspi-config nonint get_overlay_conf
```

## Maintenance Mode

The raspi-config overlay uses OverlayFS, which means writes go to RAM. You cannot simply remount `/` as writable - you must disable the overlay and reboot.

**Install helper scripts (once):**
```bash
sudo cp scripts/rw scripts/ro scripts/is_ro /usr/local/bin/
```

**Using helper scripts:**
```bash
# Check current status
is_ro  # Returns "read only" or "write access"

# Disable overlay and reboot (system becomes writable)
rw

# After making changes: re-enable overlay and reboot
ro
```

**Manual method:**
```bash
# Disable overlay and reboot
sudo raspi-config nonint do_overlayfs 1 && sudo reboot

# Make your changes (apt upgrade, config edits, etc.)

# Re-enable overlay and reboot
sudo raspi-config nonint do_overlayfs 0 && sudo reboot
```

**Note:** The often-suggested `sudo mount -o remount,rw /` does NOT work with OverlayFS - it only makes the RAM overlay writable, changes are still lost after reboot.

## Verification

```bash
# Root should be read-only
touch /test.txt  # Expected: "Read-only file system"

# /data should be writable
touch /data/test.txt && rm /data/test.txt  # Should work

# Verify symlinks
ls -la ~/img  # Points to /data/img
ls -la ~/app  # Points to /data/app

# Test slideshow
sudo systemctl restart slideshow
curl http://localhost:8080/status
```

## Rollback (Windows with WSL)

If the Pi won't boot, fix the SD card from Windows/WSL:

```powershell
# PowerShell (Admin): Attach SD card to WSL
wsl --mount \\.\PHYSICALDRIVEX --bare
```

```bash
# In WSL: Mount root partition
sudo mkdir -p /mnt/piroot
sudo mount /dev/sdd2 /mnt/piroot

# Disable overlayroot
sudo nano /mnt/piroot/etc/overlayroot.conf
# Set: overlayroot=""

# If needed, also check /etc/fstab
sudo nano /mnt/piroot/etc/fstab

# Unmount
sudo umount /mnt/piroot
```

```powershell
# PowerShell: Detach and safely remove SD card
wsl --unmount \\.\PHYSICALDRIVEX
```

Put SD card back in Pi and reboot - system will be writable again
