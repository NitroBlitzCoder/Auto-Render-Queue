# Auto Render Queue
> Set it up, walk away, and come back to finished renders.

Auto Render Queue is a Blender addon that replaces the default one-at-a-time 
render workflow with a reliable queue system. Queue multiple scenes and cameras, 
recover from crashes automatically, and get notified when your renders are done.

---

## Features

### Free
- Queue multiple scenes and/or cameras in one session
- Save and load output presets
- Pause and resume the queue at any time
- Clean progress monitor panel

### Pro
- **Crash recovery** — remembers the last completed frame and resumes automatically
- Estimated time remaining per job and overall
- Full render history log
- Discord and email notifications when jobs complete
- Auto-shutdown after queue finishes

---

## Installation

1. Download the `.zip` from [Releases](../../releases)
2. In Blender, go to `Edit > Preferences > Add-ons > Install`
3. Select the downloaded `.zip` and enable the addon

**Requires:** Blender 4.0+

---

## Usage

1. Open the panel: `Properties > Render > Auto Render Queue`
2. Add scenes or cameras to the queue
3. Set output paths and format per job
4. Hit **Start Queue** and let it run

---

## Roadmap

- [ ] Render farm / network render support
- [ ] Per-job output format overrides
- [ ] Mobile push notifications

---

## License

Free version — MIT  
Pro version — Commercial License (see [SuperHive](https://superhive.com))
