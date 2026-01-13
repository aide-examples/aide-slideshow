# Requirements

Feature list from the user's perspective. Items marked with (*) are implemented.

## Show Images

- Display images in random order (*)
- Display images in canonical order by name or timestamp
- Show all images or only a subset (*)
- Restrict shown images to those matching monitor orientation (portrait/landscape)
- Recognize current monitor orientation (tilt sensor)
- Show image as it is (*)
- Image preparation if there is no perfect fit
  - Resize (shrink, expand) (*)
  - Allow some degree of distortion (*)
  - Add border in color which is in harmony with image content (*)
  - Add image path and file name in decent small gray font (*)
  - transform images for "wrong screen orientation" - to be used with a monitor which is physically rotated by 90°
  - Offer art style borders/frames

## Energy Management

- Run on an energy efficient device (*)
- Switch the monitor off when no images shall be shown (*)
- React on motion detection
- Allow time dependent on/off periods
- Allow daylight dependent on/off periods
- Adapt brightness to ambient light conditions

## Control (How)

- Via REST API (*)
- Via HTTP UI (*)
- Via infrared remote control
- Via mouse
- Via keyboard

## Control (What)

- Play (*)
- Pause (*)
- Forward/skip (*)
- Backward
- Presentation order
- Select image subdirectory as a subset for presentation (*)
- Presentation speed (*)
- Select type of image change (slide, fade, ...)
- Monitor on/off via CEC (*)
- Monitor on/off via relay (AC power)
- Monitor on/off via Shelly plug

## Image Administration

- secure ftp access to image directory (*)
- Batch upload via API
- Interactive upload via a web API (*)

## Documentation

- Extensive documentation of the system for developers (*)
- Include architectural diagrams
- View the documentation using the app's own web UI (*)
