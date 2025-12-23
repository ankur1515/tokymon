# Face Images Storage - Tokymon POC

## 📍 Answer: Face Images Are NOT Stored

**Face images are generated programmatically in real-time, not stored as files.**

---

## 🎭 Two Face Display Systems

### 1. LED Matrix Face (MAX7219)
**Location:** `display/expressions.py`

**How it works:**
- Face is **drawn pixel-by-pixel** in real-time
- Uses drawing primitives: `draw_eyes()`, `nose_block()`, `mouth_neutral_round()`, etc.
- No image files - pure code-based rendering
- Face updates every ~16 FPS (60ms intervals)

**Key Functions:**
- `draw_face_frame()` - Main face drawing function
- `eye_full_circle()` - Draws eyes with blink animation
- `mouth_neutral_round()` - Draws mouth
- `nose_block()` - Draws nose

**Face Modes:**
- `normal` - Neutral expression
- `listening` - Eyes move left/right
- `speaking` - Mouth animates (oval shape)

---

### 2. iPhone 5s Browser UI Face
**Location:** `sessions/modules/ui_server.py` (HTML/CSS/JS embedded in code)

**How it works:**
- Face is **rendered using HTML/CSS** in the browser
- No image files - pure CSS shapes
- JavaScript polls `/api/state` every 200ms for updates
- Face updates based on `face_mode` state

**Face Elements (CSS):**
- Eyes: White circles (`.eye`)
- Pupils: Black circles (`.pupil`)
- Nose: White rectangle (`.nose`)
- Mouth: Curved border (`.mouth`)

**Face Modes:**
- `normal` - Standard face
- `greeting` - Same as normal
- `moving` - Mouth slightly larger
- `stop` - Same as normal

---

## 📸 What Images ARE Stored

### Camera Photos
**Location:** `data/photos/`

These are **camera captures** (not face images for display):
- `hw_test_20251128_180356.jpg`
- `hw_test_20251129_111903.jpg`
- etc.

**Purpose:** Hardware test photos, not face display images.

---

## 🔧 How to Modify Face Appearance

### LED Matrix Face
Edit: `display/expressions.py`

**To change:**
- Eye size: Modify `r = 3` in `eye_full_circle()`
- Eye position: Modify `LBOX` and `RBOX` constants
- Mouth shape: Edit `mouth_neutral_round()` function
- Blink timing: Adjust blink state machine logic

### iPhone UI Face
Edit: `sessions/modules/ui_server.py`

**To change:**
- Eye size: Modify `.eye` CSS width/height
- Eye position: Modify `.eye.left` and `.eye.right` CSS
- Mouth shape: Modify `.mouth` CSS border-radius
- Colors: Change `background` colors in CSS

---

## 💡 Why No Stored Images?

**Design Decision:**
- **Real-time generation** = More flexible
- **No file I/O** = Faster performance
- **Programmatic control** = Easy to animate
- **Smaller codebase** = No image assets to manage

**For POC:**
- Simple, deterministic faces
- No emotion variations needed
- Calm, non-stimulating appearance
- Same face across all modules

---

## 🎨 If You Want to Add Image-Based Faces

If you need to use actual image files:

1. **Create directory:**
   ```bash
   mkdir -p data/faces
   ```

2. **Add face images:**
   - `data/faces/neutral.png`
   - `data/faces/greeting.png`
   - `data/faces/moving.png`

3. **Modify code to load images:**
   - LED: Use PIL to load and display images
   - iPhone UI: Serve images via HTTP and use `<img>` tags

**But for POC:** Current programmatic approach is simpler and sufficient.

---

## 📊 Summary

| Face Display | Storage | Location |
|--------------|---------|----------|
| LED Matrix | **Code** (expressions.py) | Real-time pixel drawing |
| iPhone UI | **Code** (ui_server.py) | Real-time CSS rendering |
| Camera Photos | **Files** (data/photos/) | Hardware test captures |

**Bottom line:** Face images are generated on-the-fly, not stored as files.

