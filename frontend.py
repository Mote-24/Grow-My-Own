"""
Bloom - Healthy Habits App
Built with Python Flet

Install dependencies:
    pip install flet

Run:
    python bloom_app.py

Set your Anthropic API key:
    export ANTHROPIC_API_KEY="sk-ant-..."
"""

import asyncio
import time

import flet as ft
import threading
import os
import json
import urllib.request
import torch
import open_clip
import numpy as np
import cv2
from PIL import Image
import os
import csv
from google import genai
import re


# ─────────────────────────────────────────────
# THEME / PALETTE
# ─────────────────────────────────────────────
SAGE       = "#7BAE7F"
FOREST     = "#2D4A2E"
FOREST_LT  = "#3B6D11"
LEAF_DARK  = "#639922"
LEAF_BG    = "#EAF3DE"
LEAF_MID   = "#C0DD97"
CREAM      = "#FEFAE0"
CLAY       = "#C17B5A"
AMBER      = "#EF9F27"
AMBER_LT   = "#FAEEDA"
BLUE       = "#378ADD"
CORAL      = "#D85A30"
GRAY_LT    = "#F1EFE8"
GRAY_MID   = "#888780"
WHITE      = "#FFFFFF"
TEXT_PRI   = "#1A1A1A"
TEXT_SEC   = "#666660"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

nutrient_list = [0, 0, 0, 0, 0, 0, 0, 0, 0]

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.diet        = "omnivore"
        self.goal        = "less_processed"
        self.location    = "us"
        self.allergies   = []
        self.produce     = ["apple", "kale", "blueberries"]
        self.yn_state    = {}   # {index: "yes"|"no"}
        self.plant_level = 3    # 0-6
        self.setup_done  = False
        self.serving     = 1.0

    def compute_plant_level(self):
        yes_count    = sum(1 for v in self.yn_state.values() if v == "yes")
        produce_bonus = min(len(self.produce), 4)
        self.plant_level = min(6, 1 + yes_count + produce_bonus // 2)

    # ── Nutrition estimates (per 1 serving) ──
    BASE = dict(
            calcium=0, iron=0, total_fiber=0,
            protein=0, unsat_fat=0,
            vit_a=0, vit_c=0, vit_d=0, vit_e=0,
        )
        
    MAX = dict(calcium=5, iron=6, total_fiber=11, protein=14, unsat_fat=8)

    def nutrition(self):
        s = self.serving
        return {k: round(v * s, 1) for k, v in self.BASE.items()}


state = AppState()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def claude(prompt: str, max_tokens: int = 400) -> str:
    """Call the Anthropic API directly via urllib — no SDK needed."""
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"].strip()


# ─────────────────────────────────────────────
# SVG PLANT  (7 growth stages)
# ─────────────────────────────────────────────
def plant_svg(level: int) -> str:
    """Return SVG markup for the plant at the given growth level (0-6)."""

    def op(min_level):
        return "1" if level >= min_level else "0"

    fruit_apple  = f"""
      <g opacity="{op(5)}" style="cursor:pointer" onclick="apple">
        <circle cx="80" cy="108" r="14" fill="{CORAL}"/>
        <path d="M80 95 C80 92 84 90 83 88" fill="none"
              stroke="{LEAF_DARK}" stroke-width="2" stroke-linecap="round"/>
        <text x="80" y="113" text-anchor="middle" font-size="13">🍎</text>
      </g>"""

    fruit_lemon  = f"""
      <g opacity="{op(6)}" style="cursor:pointer" onclick="lemon">
        <ellipse cx="142" cy="88" rx="14" ry="11" fill="{AMBER}"/>
        <text x="142" y="93" text-anchor="middle" font-size="13">🍋</text>
      </g>"""

    return f"""
<svg width="220" height="220" viewBox="0 0 220 220" xmlns="http://www.w3.org/2000/svg">
  <!-- stem -->
  <path d="M110 200 C110 178 108 158 110 128 C112 98 105 83 110 58"
        fill="none" stroke="#5A8A3C" stroke-width="4" stroke-linecap="round"/>
  <!-- leaves -->
  <path d="M108 140 C85 128 68 112 73 93 C89 104 105 119 108 140Z"
        fill="{SAGE}" opacity="{op(2)}"/>
  <path d="M112 118 C139 106 156 90 149 70 C132 83 118 99 112 118Z"
        fill="{LEAF_DARK}" opacity="{op(2)}"/>
  <path d="M109 90 C91 79 79 63 84 48 C96 60 107 74 109 90Z"
        fill="{SAGE}" opacity="{op(3)}"/>
  <path d="M111 75 C129 63 139 48 134 35 C120 47 113 61 111 75Z"
        fill="{LEAF_DARK}" opacity="{op(3)}"/>
  <!-- petals -->
  <circle cx="110" cy="38"  r="7" fill="{AMBER_LT}" opacity="{op(4)}"/>
  <circle cx="124" cy="46"  r="7" fill="{AMBER}"    opacity="{op(4)}"/>
  <circle cx="124" cy="62"  r="7" fill="{AMBER_LT}" opacity="{op(4)}"/>
  <circle cx="110" cy="70"  r="7" fill="{AMBER}"    opacity="{op(5)}"/>
  <circle cx="96"  cy="62"  r="7" fill="{AMBER_LT}" opacity="{op(5)}"/>
  <circle cx="96"  cy="46"  r="7" fill="{AMBER}"    opacity="{op(5)}"/>
  <!-- bloom center -->
  <circle cx="110" cy="54"  r="11" fill="{CLAY}"    opacity="{op(4)}"/>
  <!-- fruits -->
  {fruit_apple}
  {fruit_lemon}
</svg>"""


PLANT_LABELS = [
    "Just sprouted 🌱",
    "First leaves appearing",
    "Growing strong",
    "In full leaf",
    "Starting to flower 🌸",
    "In full bloom",
    "Bearing fruit! 🍎",
]

YN_QUESTIONS = [
    "Drank 8 glasses of water?",
    "Ate a colorful meal?",
    "Moved your body today?",
    "Had breakfast this morning?",
]

DIET_OPTIONS     = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian"]
GENDER_OPTIONS     = {
    "male":  "Male",
    "female":    "Female",
    "other":      "Other",
}
LOCATION_OPTIONS = {
    "us":     "United States",
    "uk":     "United Kingdom",
    "asia":   "East Asia",
    "latin":  "Latin America",
    "india":  "South Asia",
    "mena":   "Middle East / North Africa",
}
ALLERGY_LIST = ["Gluten", "Tree nuts", "Dairy", "Soy", "Shellfish", "Eggs"]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def section_label(text):
    return ft.Text(text, size=12, color=TEXT_SEC, weight="w500")


def card(content, padding=16, bg=WHITE):
    return ft.Container(
        content=content,
        bgcolor=bg,
        border_radius=14,
        border=ft.Border(left=ft.BorderSide(0.5, "#DDDDDD"), right=ft.BorderSide(0.5, "#DDDDDD"), top=ft.BorderSide(0.5, "#DDDDDD"), bottom=ft.BorderSide(0.5, "#DDDDDD")),
        padding=padding,
    )


def pill_badge(text, bg=LEAF_BG, color=FOREST_LT):
    return ft.Container(
        content=ft.Text(text, size=11, color=color, weight="w500"),
        bgcolor=bg,
        border_radius=20,
        padding=ft.Padding(left=10, right=10, top=4, bottom=4),
    )


def progress_bar(value_pct, color=SAGE, height=5):
    return ft.Container(
        content=ft.Stack([
            ft.Container(bgcolor="#EEEEEE", border_radius=3, height=height, expand=True),
            ft.Container(bgcolor=color, border_radius=3, height=height,
                         width=None, expand=False,
                         # width is set as fraction — we use a Row trick below
                         ),
        ]),
        height=height,
    )


def bar_row(label, value_pct, color=SAGE):
    """A label + progress bar row."""
    return ft.Row([
        ft.Text(label, size=13, color=TEXT_PRI, width=130),
        ft.Container(
            content=ft.Row([
                ft.Container(bgcolor=color, border_radius=3, height=6,
                             width=max(2, int(value_pct * 1.6))),  # 160px = 100%
                ft.Container(bgcolor=GRAY_LT, border_radius=3, height=6, expand=True),
            ], spacing=0),
            expand=True,
        ),
        ft.Text(f"{int(value_pct)}%", size=12, color=TEXT_SEC, width=36,
                text_align="right"),
    ], spacing=10)


# ─────────────────────────────────────────────
# AI CALLS  (run in threads to avoid blocking UI)
# ─────────────────────────────────────────────
def fetch_daily_goal(callback):
    goal_label = GENDER_OPTIONS.get(state.goal, state.goal)
    prompt = (
        f"Give one small, doable daily milestone for someone whose goal is to {goal_label} "
        f"(diet: {state.diet}). "
        "It should be friendly and realistic — like 'prep apple slices before bed' "
        "or 'swap one snack for a handful of grapes.' "
        "One sentence only. No health claims. Make it feel encouraging, not prescriptive."
    )
    try:
        callback(claude(prompt, max_tokens=200))
    except Exception:
        callback("Slice some fruit and put it somewhere visible today — easy access makes all the difference!")


def fetch_meal_ideas(fruit, callback):
    produce_str  = ", ".join(state.produce) or fruit
    allergies_str = ", ".join(state.allergies) or "none"
    prompt = (
        f"Suggest 3 cheap, easy meal ideas featuring {fruit} and any of these produce items: {produce_str}. "
        f"Diet: {state.diet}. Location/cuisine preference: {state.location}. "
        f"Allergies/avoidances: {allergies_str}. "
        "Keep it friendly, practical, and accessible. No health claims. "
        "Format as a short numbered list: bold name + 1 sentence description."
    )
    try:
        callback(claude(prompt, max_tokens=400))
    except Exception:
        callback("Couldn't load ideas right now — check your API key and try again!")



def ai_food_checker(user_image):
    import torch
    import open_clip
    import csv
    import numpy as np
    from PIL import Image
    import os
    from google import genai
    import re
    import streamlit as st
    import cv2

    # 1. OPTIMIZE FOR INTEL i7 CPU
    # This forces PyTorch to use your physical CPU cores properly
    torch.set_num_threads(4) 

    SAVE_PATH = user_image

    device = "cpu" # Enforced for CPU timing
    print("Loading model weights (approx. 350MB)...")
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    model = model.to(device)
    model.eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    print("Model loaded.")

    # 2. BATCHED PROCESSING FUNCTION
    @torch.no_grad()
    def get_text_embeddings_in_batches(texts, batch_size=32):
        all_embeddings = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            tokens = tokenizer(batch).to(device)
            embeddings = model.encode_text(tokens)
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)
            all_embeddings.append(embeddings.numpy())
            
            # Simple print statement to track progress without extra libraries
            print(f"Processed {min(i + batch_size, total)}/{total} rows...", end="\r")
            
        return np.vstack(all_embeddings)

    # 3. RUN
    descriptions = []
    path = r"C:\Users\arnav\OneDrive\Desktop\app\food.csv"

    with open(path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            descriptions.append(row['description'])

    VECTOR_PATH = r"C:\Users\arnav\OneDrive\Desktop\app\query_vector.npy"

    if descriptions:
        print(f"Starting embedding generation for {len(descriptions)} items...")
        if os.path.exists(VECTOR_PATH):
            print("Loading existing vector matrix from 'query_vector.npy'...")
            vectors = np.load(VECTOR_PATH)
        else:
            print('ok ur cooked')
            vectors = get_text_embeddings_in_batches(descriptions, batch_size=32)
        print(f"\nFinished! Vector Matrix Shape: {vectors.shape}")

    image_path = user_image

    try:
        raw_image = Image.open(image_path).convert("RGB")
        
        # unsqueeze(0) adds a batch dimension, making the shape [1, 3, 224, 224]
        processed_image = preprocess(raw_image).unsqueeze(0).to(device)

        # 3. Generate and normalize the image embedding
        with torch.no_grad():
            global new_vector
            new_vector = model.encode_image(processed_image)
            new_vector = new_vector / new_vector.norm(dim=-1, keepdim=True)
            new_vector = new_vector.numpy()
    except:
         import traceback
         traceback.print_exc()

    save_path = r"C:\Users\arnav\OneDrive\Desktop\app\query_vector.npy"
    np.save(save_path, vectors)
    print(f"Successfully saved image embedding to: {save_path}")


    similarity_scores = np.dot(new_vector, vectors.T).reshape(-1)

    best_match_index = np.argmax(similarity_scores)
    highest_score = similarity_scores[best_match_index]

    # Print the result
    print(f"--- Search Result ---")
    #print(f"Query: 'lemon'")
    print(f"Closest Match in CSV: {descriptions[best_match_index]}")
    print(f"Confidence Score: {highest_score:.4f} (closer to 1.0 means a tighter match)")
    target = descriptions[best_match_index]




    # =========================================================
    # SETUP
    # =========================================================

    torch.set_num_threads(4)
    device = "cpu"

    print("Loading CLIP model...")
    model, preprocess, _ = open_clip.create_model_and_transforms(
        "ViT-B-32",
        pretrained="laion2b_s34b_b79k"
    )
    model = model.to(device)
    model.eval()

    tokenizer = open_clip.get_tokenizer("ViT-B-32")


    # =========================================================
    # STEP 1: FOOD TYPE CLASSIFICATION (NEW LAYER)
    # =========================================================

    FOOD_CATEGORIES = [
        "a fruit on a plate",
        "a whole citrus fruit",
        "a lemon",
        "a pile of vegetables on a plate",
        "a pile of rice or grains on a plate",
        "a cooked solid meal on a plate",
        "a dessert or baked good",
        "a soda can",
        "a beverage bottle",
        "a drink container",
        "a liquid soup or broth",
    ]

    def classify_food_type(image):
        image_input = preprocess(image).unsqueeze(0).to(device)
        text_tokens = tokenizer(FOOD_CATEGORIES).to(device)

        with torch.no_grad():
            img_feat = model.encode_image(image_input)
            txt_feat = model.encode_text(text_tokens)

            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
            txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)

            sims = (img_feat @ txt_feat.T).squeeze(0)

        idx = torch.argmax(sims).item()
        return FOOD_CATEGORIES[idx]


    # =========================================================
    # STEP 2: SAM SEGMENTATION
    # =========================================================

    def get_food_mask(image_path):
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        device_sam = "cuda" if torch.cuda.is_available() else "cpu"
        print("CWD:", os.getcwd())
        sam2_checkpoint = os.path.join(BASE_DIR, "checkpoints", "sam2_hiera_small.pt")
        model_cfg = "configs/sam2/sam2_hiera_s"

        sam_model = build_sam2(model_cfg, sam2_checkpoint, device=device_sam, apply_postprocessing=False)
        predictor = SAM2ImagePredictor(sam_model)

        image = np.array(Image.open(image_path).convert("RGB"))
        predictor.set_image(image)

        h, w, _ = image.shape
        points = np.array([[w // 2, h // 2]])
        labels = np.array([1])

        masks, scores, _ = predictor.predict(
            point_coords=points,
            point_labels=labels,
            multimask_output=True
        )

        best = np.argmax(scores)
        mask = masks[best].astype(np.uint8)

        # cleanup
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask.astype(bool)


    # =========================================================
    # STEP 3: DEPTH ESTIMATION
    # =========================================================

    def get_depth_map(image_path):
        from depth_anything_v2.dpt import DepthAnythingV2

        model = DepthAnythingV2(
            encoder="vits",
            features=64,
            out_channels=[48, 96, 192, 384]
        )

        depth_checkpoint = os.path.join(BASE_DIR, "checkpoints", "depth_anything_v2_vits.pth")
        model.load_state_dict(
            torch.load(depth_checkpoint, map_location=device)
        )

        model.to(device).eval()

        image = cv2.imread(image_path)

        depth = model.infer_image(image).astype(np.float32)

        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

        return depth


    # =========================================================
    # STEP 4: GEOMETRIC VOLUME ESTIMATION
    # =========================================================

    def estimate_volume(mask, depth, pixel_to_cm=0.05):

        h, w = mask.shape
        depth = cv2.resize(depth, (w, h))

        # plate baseline
        boundary = cv2.dilate(mask.astype(np.uint8), np.ones((7,7)))
        boundary = boundary - mask.astype(np.uint8)

        values = depth[boundary == 1]
        plate_depth = np.median(values) if len(values) > 10 else np.median(depth)

        #height = np.clip(plate_depth - depth, 0, None)
        height = np.abs(plate_depth - depth)

        height *= mask

        pixel_area = pixel_to_cm ** 2
        volume = np.sum(height * pixel_area)

        print("Plate depth:", plate_depth)
        print("Max depth:", depth.max())
        print("Min depth:", depth.min())
        print("Max height:", np.max(height))
        print("Mask pixels:", np.sum(mask))
        print("Pixel area:", pixel_area)
        print("Volume:", volume)
        print("Median food depth:", np.median(depth[mask]))
        print("Mean food depth:", np.mean(depth[mask]))


        return volume


    # =========================================================
    # STEP 5: ROUTING ENGINE (IMPORTANT PART)
    # =========================================================

    def estimate_food_mass(image_path, density=1.05):

        image = Image.open(image_path).convert("RGB")

        print("[1/4] Classifying food type...")
        food_type = classify_food_type(image)
        print("Detected:", food_type)

        # -----------------------------------------------------
        # CASE 1: CONTAINERS (soda cans, bottles)
        # -----------------------------------------------------
        if "can" in food_type or "bottle" in food_type or "drink container" in food_type:
            print("[ROUTE] Container detected → using database estimate")

            # standard soda can fallback
            volume = 355
            mass = 355

            return volume, mass, food_type

        # -----------------------------------------------------
        # CASE 2: LIQUID FOODS
        # -----------------------------------------------------
        if "liquid" in food_type or "soup" in food_type:
            print("[ROUTE] Liquid detected → hybrid estimation")

            mask = get_food_mask(image_path)
            depth = get_depth_map(image_path)

            volume = estimate_volume(mask, depth)
            mass = volume * 1.0

            return volume, mass, food_type

        # -----------------------------------------------------
        # CASE 3: SOLID FOODS (default geometry model)
        # -----------------------------------------------------
        print("[ROUTE] Solid food detected → geometric estimation")

        mask = get_food_mask(image_path)
        depth = get_depth_map(image_path)

        volume = estimate_volume(mask, depth)
        mass = volume * density

        return volume, mass, food_type


    # =========================================================
    # RUN
    # =========================================================

    if __name__ == "__main__":

        IMAGE_PATH = user_image

        volume, mass, food_type = estimate_food_mass(IMAGE_PATH)

        print("\n===== FINAL RESULT =====")
        print("Type:", food_type)
        print(f"Volume: {volume:.2f} cm³")
        print(f"Mass:   {mass:.2f} g")

    with open (path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['description'] == target:
                fdc_id = row['fdc_id']

    path2 = r"C:\Users\arnav\OneDrive\Desktop\app\food_nutrient.csv"
    nutrient_id_list = []
    amount_list = []

    with open(path2, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['fdc_id'] == fdc_id:
                nutrient_id_list.append(row['nutrient_id'])
                amount_list.append(row['amount'])
                    
    with open(r"C:\Users\arnav\OneDrive\Desktop\app\analyze.csv", 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Nutrient ID', 'Amount', 'Nutrient Name'])
        for nutrient, amount in zip(nutrient_id_list, amount_list):
            with open(r"C:\Users\arnav\OneDrive\Desktop\app\nutrient.csv", "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['nutrient_nbr'] == nutrient:
                        writer.writerow([nutrient, amount, row['name']])

    with open(r"C:\Users\arnav\OneDrive\Desktop\app\analyze.csv", 'r', encoding='utf-8', newline='') as file:
        reader = csv.reader(file)
        header = next(reader)
        for row in reader:
            if row[0] == '208':
                calories = float(row[1])

    print(f"Calories: {calories}")
    relative_mass = mass / 100
    relative_calories = calories * relative_mass

    print(f"Relative Calories: {relative_calories}")
    return descriptions[best_match_index]



from google import genai
import json
import re

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def get_serving_options(food):

    prompt = f"""
Food: {food}

Return exactly 3 realistic serving sizes.

Rules:
- Use common household servings.
- Include approximate grams.
- Increasing size.
- Return ONLY JSON.

Example:

[
    {{"label":"Small apple", "grams":120}},
    {{"label":"Medium apple", "grams":180}},
    {{"label":"Large apple", "grams":250}}
]
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    text = response.text.strip()

    # Remove markdown if Gemini adds it
    text = re.sub(r"```json|```", "", text).strip()
    print(response.text)
    return json.loads(text)
# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
def main(page: ft.Page):
    # FUNCTIONS:
    def refresh_log():
        if not log_list_ref.current:
            return

        log_list_ref.current.controls = [
            ft.Text(item, size=13, color=TEXT_PRI)
            for item in food_log
        ]
        page.update()

    page.title        = "Grow My Own 🌱"
    page.bgcolor      = CREAM
    page.padding      = 0
    page.window.width = 420
    page.window.min_width = 380
    page.fonts        = {}
    page.theme        = ft.Theme(color_scheme_seed=SAGE)
    loading_text = ft.Text("Analyzing...", size=16)

    loading_dialog = ft.AlertDialog(
        modal=True,
        content=ft.Container(
            width=250,
            padding=20,
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    loading_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                tight=True,
            ),
        ),
    )

    page.overlay.append(loading_dialog)
    # Initialize without parameters or appending to overlay
    pick_files_dialog = ft.FilePicker()


    serving_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[]
)

    page.overlay.append(serving_dialog)

    def show_serving_dialog(food, options):

        hide_loading()


        serving_dropdown.options = [
            ft.dropdown.Option(
                key=str(x["grams"]),
                text=f'{x["label"]} (~{x["grams"]} g)'
            )
            for x in options
        ]

        if not options:
            print("No serving options returned!")
            return

        serving_dropdown.value = str(options[0]["grams"])    
    

        def confirm(e):

            grams = float(serving_dropdown.value)

            relative_mass = grams / 100

            food_log.append(food)

            add_food_to_nutrition(food)

            # Scale nutrients
            for nutrient in state.BASE:
                state.BASE[nutrient] *= relative_mass

            refresh_log()
            refresh_nutrition()

            serving_dialog.open = False

            page.update()

        serving_dialog.title = ft.Text(food)

        serving_dialog.content = ft.Column(
            [
                ft.Text("Choose the closest serving size:"),

                serving_dropdown,
            ],
            tight=True,
        )

        serving_dialog.actions = [
            ft.ElevatedButton("Confirm", on_click=confirm)
        ]

        serving_dialog.open = True

        page.update()

    def show_loading(message="Loading..."):
        loading_text.value = message
        loading_dialog.open = True
        print("show loading")
        page.update()

    def hide_loading():
        loading_dialog.open = False
        print("hide loading")
        page.update()
    
    # This must be an async function to capture the new file picker returns
    

    async def upload_food_photo(e):
        result = await pick_files_dialog.pick_files(
            allow_multiple=False,
            allowed_extensions=["jpg", "jpeg", "png"],
         )

        if not result:
             return
        
      
        show_loading("Analyzing your photo...This may take a minute.")

        file = result[0]
        detected_food["value"] = ""

        def process_ai_analysis():
            try:
                target = ai_food_checker(file.path)
                detected_food["value"] = target
                # show_confirmation_dialog() hides the loader and opens confirm
                page.run_thread(show_confirmation_dialog)
            except Exception as err:
                print(f"AI Error: {err}")
                page.run_thread(hide_loading)

        threading.Thread(target=process_ai_analysis, daemon=True).start()


    # ── Shared refs ──────────────────────────
    tab_garden_btn    = ft.Ref[ft.TextButton]()
    tab_nutrition_btn = ft.Ref[ft.TextButton]()
    tab_log_btn       = ft.Ref[ft.TextButton]()
    garden_panel      = ft.Ref[ft.Column]()
    nutrition_panel   = ft.Ref[ft.Column]()
    log_panel       = ft.Ref[ft.Column]()
    plant_svg_ctrl    = ft.Ref[ft.Image]()
    plant_label_ctrl  = ft.Ref[ft.Text]()
    daily_goal_ctrl   = ft.Ref[ft.Text]()
    produce_chips_row = ft.Ref[ft.Row]()
    streak_ctrl       = ft.Ref[ft.Text]()
    food_autocomplete_ref = ft.Ref[ft.AutoComplete]()
    loading_text_ref = ft.Ref[ft.Text]()
    loading_dialog_ref = ft.Ref[ft.AlertDialog]()
    detected_food = {"value": ""}
    serving_options = []
    selected_grams = 100

    serving_dropdown = ft.Dropdown(width=250)
    confirm_text = ft.Text()

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Is this correct?"),
        content=confirm_text,
    )
    page.overlay.append(confirm_dialog)

    def confirm_yes(e):
        food = detected_food["value"]

        food_log.append(food)
        add_food_to_nutrition(food)

        refresh_log()
        refresh_nutrition()

        confirm_dialog.open = False

        hide_loading()
        loading_dialog.open = False
        page.update()
    
    def confirm_no(e):
        confirm_dialog.open = False

        food_autocomplete_ref.current.value = detected_food["value"]

        page.update()


    def show_confirmation_dialog():
        hide_loading()
        loading_dialog.open = False

        confirm_text.value = f"We detected:\n\n{detected_food['value']}"

        confirm_dialog.actions = [
            ft.ElevatedButton("✓ Correct", on_click=confirm_yes),
            ft.OutlinedButton("✗ Wrong", on_click=confirm_no),
        ]

        confirm_dialog.open = True
        page.update()

    # Nutrition refs
    calcium_ctrl    = ft.Ref[ft.Text]()
    iron_ctrl  = ft.Ref[ft.Text]()
    total_fiber_ctrl  = ft.Ref[ft.Text]()
    protein_ctrl      = ft.Ref[ft.Text]()
    unsat_fat_ctrl    = ft.Ref[ft.Text]()
    nutrition_note    = ft.Ref[ft.Text]()
    serving_label     = ft.Ref[ft.Text]()


    food_log = []
    food_input_ref = ft.Ref[ft.TextField]()
    log_list_ref = ft.Ref[ft.Column]()

    # Vitamin bar refs — store as plain dicts
    vit_bars   = {}   # {"vitA": ft.Container, ...}
    vit_labels = {}   # {"vitA": ft.Text, ...}

    # Meal dialog refs
    meal_title_ctrl   = ft.Ref[ft.Text]()
    meal_body_ctrl    = ft.Ref[ft.Text]()
    meal_dialog       = ft.Ref[ft.AlertDialog]()

    # YN card refs
    yn_cards = {}   # {i: {"yes_btn": ..., "no_btn": ..., "card_container": ...}}

    # Setup dialog refs
    setup_dialog      = ft.Ref[ft.AlertDialog]()
    age_dropdown     = ft.Ref[ft.Dropdown]()
    gender_dropdown     = ft.Ref[ft.Dropdown]()
    location_dropdown = ft.Ref[ft.Dropdown]()
    allergy_chips_row = ft.Ref[ft.Row]()
    overall_score_ctrl = ft.Ref[ft.Text]()
    selected_allergies = set()

    # ── Plant update ─────────────────────────
    def update_plant():
        state.compute_plant_level()
        svg_src = plant_svg(state.plant_level)
        if plant_svg_ctrl.current:
            plant_svg_ctrl.current.src = None
            plant_svg_ctrl.current.src_base64 = None
            # Flet Image can render SVG strings via content
            plant_svg_ctrl.current.src = f"data:image/svg+xml,{svg_src.replace('#', '%23').replace(' ', '%20')}"
        if plant_label_ctrl.current:
            plant_label_ctrl.current.value = PLANT_LABELS[min(state.plant_level, 6)]
        page.update()

    # ── Produce chips ─────────────────────────
    def rebuild_produce_chips():
        chips = []
        for i, item in enumerate(state.produce):
            idx = i  # capture

            def remove(e, captured_idx=idx):
                state.produce.pop(captured_idx)
                rebuild_produce_chips()
                update_nutrition_note()
                update_plant()

            chips.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(item, size=13, color=FOREST),
                        ft.IconButton("close", icon_size=14, icon_color=FOREST_LT,
                                      on_click=remove, padding=0, width=20, height=20),
                    ], spacing=4, tight=True),
                    bgcolor=LEAF_BG,
                    border_radius=20,
                    padding=ft.Padding(left=12, right=4, top=4, bottom=4),
                )
            )
        if produce_chips_row.current:
            produce_chips_row.current.controls = chips
            page.update()

    # ── Nutrition note ────────────────────────
    def update_nutrition_note():
        listed = ", ".join(state.produce) if state.produce else "your logged produce"
        if nutrition_note.current:
            nutrition_note.current.value = (
                f"Estimates based on: {listed}. Values are approximations — "
                "individual food sizes vary. Tap a fruit on your garden to get meal ideas!"
            )
            page.update()

    # ── Nutrition numbers ─────────────────────
    def refresh_nutrition():
        n = state.nutrition()
        refs = {
            "calcium": calcium_ctrl, "iron": iron_ctrl,
            "total_fiber": total_fiber_ctrl, "protein": protein_ctrl,
            "unsat_fat": unsat_fat_ctrl,
        }
        labels = {
            "calcium": "calcium", "iron": "iron",
            "total_fiber": "total_fiber", "protein": "protein", "unsat_fat": "unsat_fat",
        }
        for key, ref in refs.items():
            if ref.current:
                ref.current.value = str(n[key])

        s = state.serving
        vit_data = {
            "vitA": min(100, round(state.BASE["vit_a"] * s)),
            "vitC": min(100, round(state.BASE["vit_c"] * s)),
            "vitD": min(100, round(state.BASE["vit_d"] * s)),
            "vitE": min(100, round(state.BASE["vit_e"] * s)),
        }
        for key, pct in vit_data.items():
            if key in vit_bars and vit_bars[key]:
                vit_bars[key].width = max(2, int(pct * 1.6))
            if key in vit_labels and vit_labels[key]:
                vit_labels[key].value = f"{pct}%"
        page.update()

    # ── YN toggle ────────────────────────────
    def make_yn_toggle(idx):
        def on_yes(e):
            state.yn_state[idx] = "yes"
            yn_cards[idx]["yes_btn"].style = ft.ButtonStyle(
                bgcolor=SAGE, color=WHITE,
                shape=ft.RoundedRectangleBorder(radius=6),
            )
            yn_cards[idx]["no_btn"].style = ft.ButtonStyle(
                bgcolor=GRAY_LT, color=TEXT_SEC,
                shape=ft.RoundedRectangleBorder(radius=6),
            )
            yn_cards[idx]["card_container"].bgcolor = LEAF_BG
            update_plant()

        def on_no(e):
            state.yn_state[idx] = "no"
            yn_cards[idx]["no_btn"].style = ft.ButtonStyle(
                bgcolor=AMBER_LT, color="#854F0B",
                shape=ft.RoundedRectangleBorder(radius=6),
            )
            yn_cards[idx]["yes_btn"].style = ft.ButtonStyle(
                bgcolor=GRAY_LT, color=TEXT_SEC,
                shape=ft.RoundedRectangleBorder(radius=6),
            )
            yn_cards[idx]["card_container"].bgcolor = WHITE
            update_plant()

        btn_style = ft.ButtonStyle(
            bgcolor=GRAY_LT, color=TEXT_SEC,
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(left=8, right=8, top=4, bottom=4),
        )
        yes_btn = ft.ElevatedButton("Yes", style=btn_style, on_click=on_yes,
                                    width=48, height=30)
        no_btn  = ft.ElevatedButton("No",  style=btn_style, on_click=on_no,
                                    width=48, height=30)

        container = ft.Container(
            content=ft.Row([
                ft.Text(YN_QUESTIONS[idx], size=13, color=TEXT_PRI, expand=True),
                ft.Row([yes_btn, no_btn], spacing=4, tight=True),
            ], alignment="spaceBetween"),
            bgcolor=WHITE,
            border_radius=12,
            border=ft.Border(left=ft.BorderSide(0.5, "#DDDDDD"), right=ft.BorderSide(0.5, "#DDDDDD"), top=ft.BorderSide(0.5, "#DDDDDD"), bottom=ft.BorderSide(0.5, "#DDDDDD")),
            padding=ft.Padding(left=12, right=12, top=10, bottom=10),
        )
        yn_cards[idx] = {"yes_btn": yes_btn, "no_btn": no_btn, "card_container": container}
        return container

    # ── Meal dialog ───────────────────────────
    def open_meal_modal(fruit):
        if meal_title_ctrl.current:
            meal_title_ctrl.current.value = f"Meal ideas with {fruit}"
        if meal_body_ctrl.current:
            meal_body_ctrl.current.value = "Finding ideas for you..."
        if meal_dialog.current:
            meal_dialog.current.open = True
        page.update()

        def on_result(text):
            if meal_body_ctrl.current:
                meal_body_ctrl.current.value = text
            page.update()

        threading.Thread(target=fetch_meal_ideas, args=(fruit, on_result), daemon=True).start()

    def close_meal_dialog(e):
        if meal_dialog.current:
            meal_dialog.current.open = False
        page.update()

    meal_dialog_ctrl = ft.AlertDialog(
        ref=meal_dialog,
        title=ft.Text("", ref=meal_title_ctrl, size=16,
                      weight="w500", color=TEXT_PRI),
        content=ft.Container(
            content=ft.Text("", ref=meal_body_ctrl, size=14, color=TEXT_PRI,
                            selectable=True),
            width=300, padding=ft.Padding(left=0, right=0, top=8, bottom=8),
        ),
        actions=[ft.TextButton("Close", on_click=close_meal_dialog)],
        actions_alignment="end",
    )
    page.overlay.append(meal_dialog_ctrl)

    # ── Produce input ──────────────────────────
    produce_field = ft.TextField(
        hint_text="e.g. apple, spinach, mango...",
        border_radius=10,
        border_color="#CCCCCC",
        focused_border_color=SAGE,
        text_size=14,
        expand=True,
        bgcolor=WHITE,
        color=TEXT_PRI,
    )

    def on_add_produce(e):
        raw = produce_field.value.strip()
        if not raw:
            return
        items = [s.strip().lower() for s in raw.split(",") if s.strip()]
        for item in items:
            if item and item not in state.produce:
                state.produce.append(item)
        produce_field.value = ""
        rebuild_produce_chips()
        update_nutrition_note()
        update_plant()

    produce_field.on_submit = on_add_produce

    # ── Tab switching ─────────────────────────
    def switch_tab(tab_name):
        if garden_panel.current:
            garden_panel.current.visible = (tab_name == "garden")

        if nutrition_panel.current:
            nutrition_panel.current.visible = (tab_name == "nutrition")

        if log_panel.current:
            log_panel.current.visible = (tab_name == "log")

        page.update()

    # ── Serving slider ────────────────────────
    def on_serving_change(e):
        state.serving = float(e.control.value)
        if serving_label.current:
            serving_label.current.value = f"{state.serving:.1f}×"
        refresh_nutrition()

    # ── Setup dialog ──────────────────────────
    allergy_chip_controls = {}

    def toggle_allergy(name, container):
        def handler(e):
            if name in selected_allergies:
                selected_allergies.discard(name)
                container.bgcolor = GRAY_LT
                container.border  = ft.Border(left=ft.BorderSide(0.5, "#CCCCCC"), right=ft.BorderSide(0.5, "#CCCCCC"), top=ft.BorderSide(0.5, "#CCCCCC"), bottom=ft.BorderSide(0.5, "#CCCCCC"))
                container.content.color = TEXT_SEC
            else:
                selected_allergies.add(name)
                container.bgcolor = LEAF_BG
                container.border  = ft.Border(left=ft.BorderSide(0.5, SAGE), right=ft.BorderSide(0.5, SAGE), top=ft.BorderSide(0.5, SAGE), bottom=ft.BorderSide(0.5, SAGE))
                container.content.color = FOREST
            page.update()
        return handler

    def build_allergy_chips():
        chips = []
        for name in ALLERGY_LIST:
            label = ft.Text(name, size=13, color=TEXT_SEC)
            chip  = ft.Container(
                content=label,
                bgcolor=GRAY_LT,
                border_radius=20,
                border=ft.Border(left=ft.BorderSide(0.5, "#CCCCCC"), right=ft.BorderSide(0.5, "#CCCCCC"), top=ft.BorderSide(0.5, "#CCCCCC"), bottom=ft.BorderSide(0.5, "#CCCCCC")),
                padding=ft.Padding(left=12, right=12, top=5, bottom=5),
            )
            chip.on_click = toggle_allergy(name, chip)
            allergy_chip_controls[name] = chip
            chips.append(chip)
        return chips

    def finish_setup(e):
        state.age     = (age_dropdown.current.value or "18")
        state.gender     = gender_dropdown.current.value or "Male"
        state.location = location_dropdown.current.value or "us"
        state.allergies = list(selected_allergies)
        state.setup_done = True
        if setup_dialog.current:
            setup_dialog.current.open = False
        page.update()
        # fetch AI daily goal
        if daily_goal_ctrl.current:
            daily_goal_ctrl.current.value = "Generating your goal..."
        page.update()
        threading.Thread(
            target=fetch_daily_goal,
            args=(lambda text: (
                setattr(daily_goal_ctrl.current, "value", text),
                page.update()
            ) if daily_goal_ctrl.current else None),
            daemon=True
        ).start()

    setup_dialog_ctrl = ft.AlertDialog(
        ref=setup_dialog,
        modal=True,
        title=ft.Column([
            ft.Text("🌱", size=28),
            ft.Text("Welcome to Grow My Own", size=18, weight="w500", color=FOREST),
            ft.Text("Let's personalize your garden.", size=13, color=TEXT_SEC),
        ], spacing=4, tight=True),
        content=ft.Container(
            content=ft.Column([
                ft.Text("Age", size=13, weight="w500", color=TEXT_PRI),
                ft.Dropdown(
                    ref=age_dropdown,
                    options=[ft.dropdown.Option(str(i)) for i in range(13, 101)],
                    value="18",
                    border_color="#CCCCCC",
                    focused_border_color=SAGE,
                    text_size=14,
                    color=TEXT_PRI,


                ),
                ft.Text("Gender", size=13, weight="w500", color=TEXT_PRI),
                ft.Dropdown(
                    ref=gender_dropdown,
                    options=[ft.dropdown.Option(k, v) for k, v in GENDER_OPTIONS.items()],
                    value="Male",
                    border_color="#CCCCCC",
                    focused_border_color=SAGE,
                    text_size=14,
                    color=TEXT_PRI,
                ),
                ft.Text("Location (for meal ideas)", size=13, weight="w500", color=TEXT_PRI),
                ft.Dropdown(
                    ref=location_dropdown,
                    options=[ft.dropdown.Option(k, v) for k, v in LOCATION_OPTIONS.items()],
                    value="us",
                    border_color="#CCCCCC",
                    focused_border_color=SAGE,
                    text_size=14,
                    color=TEXT_PRI,
                ),
                ft.Text("Allergies / avoidances", size=13, weight="w500", color=TEXT_PRI),
                ft.Row(build_allergy_chips(), wrap=True, spacing=6, run_spacing=6),
            ], spacing=8, scroll="auto"),
            width=340,
            height=420,
        ),
        actions=[
            ft.ElevatedButton(
                "Start my garden →",
                bgcolor=FOREST,
                color=WHITE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                on_click=finish_setup,
            )
        ],
        actions_alignment="center",
    )
    page.overlay.append(setup_dialog_ctrl)

    # ─────────────────────────────────────────
    # BUILD GARDEN TAB
    # ─────────────────────────────────────────
    def build_garden_tab():
        #plant_img = ft.Image(
        #    ref=plant_svg_ctrl,
        #    src=f"data:image/svg+xml,{plant_svg(state.plant_level).replace('#', '%23').replace(' ', '%20')}",
        #    width=220, height=220,
        #    fit="contain" if hasattr(ft, "ImageFit") else "contain",
        #)
        plant_img = ft.Text("🌱", size=100)
        # Fruit click buttons (overlay on top of SVG)
        apple_btn = ft.ElevatedButton(
            "🍎 apple", width=80, height=32,
            style=ft.ButtonStyle(
                bgcolor=CORAL, color=WHITE,
                shape=ft.RoundedRectangleBorder(radius=16),
                padding=0,
            ),
            on_click=lambda e: open_meal_modal("apple"),
        )
        lemon_btn = ft.ElevatedButton(
            "🍋 lemon", width=80, height=32,
            style=ft.ButtonStyle(
                bgcolor=AMBER, color=WHITE,
                shape=ft.RoundedRectangleBorder(radius=16),
                padding=0,
            ),
            on_click=lambda e: open_meal_modal("lemon"),
        )

        garden_box = ft.Container(
            content=ft.Column([
                plant_img,
                ft.Container(
                    content=ft.Text("", ref=plant_label_ctrl, size=12,
                                    color=FOREST, weight="w500"),
                    alignment=ft.Alignment(0, 0),
                    padding=ft.Padding(left=0, right=0, top=8, bottom=0),
                ),
            ], horizontal_alignment="center", spacing=4),
            bgcolor=LEAF_BG,
            border_radius=16,
            padding=20,
        )

        overall_score = 82  # replace with your calculated score

        daily_goal_card = card(
            ft.Column([
                section_label("OVERALL SCORE"),
                ft.Container(height=8),

            ft.Container(
                content=ft.Text(
                    str(overall_score),
                    size=40,
                    weight="w600",
                    color=FOREST,
                    text_align="center",
                ),
                alignment=ft.Alignment(0, 0),
                bgcolor=LEAF_BG,
                border_radius=16,
                padding=20,
            ),
    ], horizontal_alignment="center"),
            
        )
                    

        yn_grid = ft.Column(
            [make_yn_toggle(i) for i in range(len(YN_QUESTIONS))],
            spacing=8,
        )

        produce_row = ft.Row([
            produce_field,
            ft.ElevatedButton(
                "Add",
                style=ft.ButtonStyle(
                    bgcolor=SAGE, color=WHITE,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                ),
                height=44,
                on_click=on_add_produce,
            ),
        ], spacing=8)

        produce_chips = ft.Row(ref=produce_chips_row, wrap=True, spacing=6, run_spacing=6)
        rebuild_produce_chips()

        return ft.Column(
            ref=garden_panel,
            controls=[
                ft.Container(height=4),
                ft.Container(garden_box, padding=ft.Padding(left=16, right=16, top=0, bottom=0)),
                ft.Container(daily_goal_card, padding=ft.Padding(left=16, right=16, top=0, bottom=0)),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Column([
                        section_label("HOW ARE YOU DOING TODAY?"),
                        ft.Container(height=8),
                        yn_grid,
                        ft.Container(height=16),
                        section_label("WHAT PRODUCE DID YOU HAVE?"),
                        ft.Container(height=8),
                        produce_row,
                        ft.Container(height=8),
                        produce_chips,
                    ]),
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                ),
                ft.Container(height=16),
            ],
            scroll="auto",
            spacing=0,
            visible=True,
        )

    # ─────────────────────────────────────────
    # BUILD NUTRITION TAB
    # ─────────────────────────────────────────
    def make_macro_card(label, ref_ctrl, unit, bar_color=SAGE):
        return ft.Container(
            content=ft.Column([
                ft.Text(label, size=12, color=TEXT_SEC),
                ft.Row([
                    ft.Text("—", ref=ref_ctrl, size=22,
                            weight="w500", color=TEXT_PRI),
                    ft.Text(unit, size=12, color=TEXT_SEC),
                ], spacing=3, vertical_alignment="end"),
                ft.Container(
                    content=ft.Row([
                        ft.Container(bgcolor=bar_color, border_radius=3, height=5, width=60),
                        ft.Container(bgcolor=GRAY_LT, border_radius=3, height=5, expand=True),
                    ], spacing=0),
                    margin=ft.Margin(left=0, right=0, top=8, bottom=0),
                ),
            ], spacing=2),
            bgcolor=WHITE,
            border_radius=14,
            border=ft.Border(left=ft.BorderSide(0.5, "#DDDDDD"), right=ft.BorderSide(0.5, "#DDDDDD"), top=ft.BorderSide(0.5, "#DDDDDD"), bottom=ft.BorderSide(0.5, "#DDDDDD")),
            padding=14,
            expand=True,
        )

    VIT_KEY_MAP = {"vitA": "vit_a", "vitC": "vit_c", "vitD": "vit_d", "vitE": "vit_e"}

    def make_vit_row(label, key, color=SAGE):
        base_key = VIT_KEY_MAP.get(key, key)
        pct  = min(100, round(state.BASE[base_key] * state.serving))
        bar  = ft.Container(bgcolor=color, border_radius=3, height=6,
                            width=max(2, int(pct * 1.6)))
        lbl  = ft.Text(f"{pct}%", size=12, color=TEXT_SEC, width=36,
                       text_align="right")
        vit_bars[key]   = bar
        vit_labels[key] = lbl
        bg = ft.Container(bgcolor=GRAY_LT, border_radius=3, height=6, expand=True)
        return ft.Row([
            ft.Text(label, size=13, color=TEXT_PRI, width=110),
            ft.Container(
                content=ft.Row([bar, bg], spacing=0),
                expand=True,
            ),
            lbl,
        ], spacing=10)

    def build_nutrition_tab():
        n = state.nutrition()

        macro_row1 = ft.Row([
            make_macro_card("Calcium",   calcium_ctrl,   "mg",  SAGE),
            make_macro_card("Iron", iron_ctrl, "mg",  SAGE),
        ], spacing=8)

        macro_row2 = ft.Row([
            make_macro_card("Total fiber",     total_fiber_ctrl, "g",  AMBER),
            make_macro_card("Plant protein",   protein_ctrl,     "g",  BLUE),
        ], spacing=8)

        macro_row3 = ft.Row([
            make_macro_card("Unsaturated fats", unsat_fat_ctrl,  "g",  CORAL),
        ])

        vit_section = ft.Column([
            section_label("KEY VITAMINS (% DAILY VALUE)"),
            ft.Container(height=8),
            make_vit_row("Vitamin A", "vitA", AMBER),
            make_vit_row("Vitamin C", "vitC", SAGE),
            make_vit_row("Vitamin D", "vitD", BLUE),
            make_vit_row("Vitamin E", "vitE", CORAL),
        ], spacing=10)

        note = ft.Text(
            ref=nutrition_note,
            value="",
            size=11, color=TEXT_SEC, italic=True, no_wrap=False,
        )
        update_nutrition_note()

        # Set initial values
        for ref, key in [
            (calcium_ctrl, "calcium"), (iron_ctrl, "iron"),
            (total_fiber_ctrl, "total_fiber"), (protein_ctrl, "protein"),
            (unsat_fat_ctrl, "unsat_fat"),
        ]:
            if ref.current:
                ref.current.value = str(n[key])

        return ft.Column(
            ref=nutrition_panel,
            controls=[
                ft.Container(height=4),
                #ft.Container(serving_row,  padding=ft.Padding(left=16, right=16, top=0, bottom=0)),
                ft.Container(
                    content=ft.Column([macro_row1, macro_row2, macro_row3], spacing=8),
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                ),
                ft.Container(
                    content=vit_section,
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                    margin=ft.Margin(left=0, right=0, top=8, bottom=0),
                ),
                ft.Container(
                    content=note,
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                    margin=ft.Margin(left=0, right=0, top=8, bottom=16),
                ),
            ],
            scroll="auto",
            spacing=8,
            visible=False,
        )

    def load_suggestions_from_csv(file_path):
        """Reads a CSV and converts it to Flet AutoCompleteSuggestion objects."""
        file_path = r"C:\Users\arnav\OneDrive\Desktop\app\food.csv"
        suggestions = []
        try:
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Replace 'name' with the exact column header of your food items
                    if 'description' in row:
                        food_item = row['description']
                        suggestions.append(
                            ft.AutoCompleteSuggestion(key=food_item, value=food_item)
                        )
        except FileNotFoundError:
            print(f"Error: Could not find the file at {file_path}")
        
        return suggestions


    def build_log_tab():
        csv_file =  r"C:\Users\arnav\OneDrive\Desktop\app\food.csv"
        suggestions_list = load_suggestions_from_csv(csv_file)
        type_card = card(
            ft.Column([
                section_label("LOG A FOOD"),

                ft.Container(height=8),

                ft.AutoComplete( 
                    ref=food_autocomplete_ref, 
                    suggestions=suggestions_list,
                    suggestions_max_height=200, 
                
            ), 


                ft.Container(height=8),

                ft.ElevatedButton(
                    "Add Food",
                    icon="add",
                    bgcolor=SAGE,
                    color=WHITE,
                    on_click=add_food,
                ),
            ])
        )

        photo_card = card(
            ft.Column([
                section_label("SCAN A MEAL"),

                ft.Container(height=8),

                ft.Text(
                    "Take a photo and we'll identify the foods.",
                    size=13,
                    color=TEXT_SEC,
                ),

                ft.Container(height=8),

                ft.ElevatedButton(
                    "📷 Upload Photo",
                    bgcolor=BLUE,
                    color=WHITE,
                    on_click=upload_food_photo,
                ),
            ])
        )

        history_card = card(
            ft.Column([
                section_label("TODAY'S LOG"),

                ft.Container(height=8),

                ft.Column(
                    ref=log_list_ref,
                    spacing=8,
                ),
            ])
        )

        return ft.Column(
            ref=log_panel,
            controls=[
                ft.Container(height=4),

                ft.Container(
                    type_card,
                    padding=ft.Padding(16, 0, 16, 0),
                ),

                ft.Container(height=8),

                ft.Container(
                    photo_card,
                    padding=ft.Padding(16, 0, 16, 0),
                ),

                ft.Container(height=8),

                ft.Container(
                    history_card,
                    padding=ft.Padding(16, 0, 16, 16),
                ),
            ],
            visible=False,
            scroll="auto",
        )

    # ─────────────────────────────────────────
    # BUILD HEADER
    # ─────────────────────────────────────────
    def build_header():
        return ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Text("bl", size=22, weight="w500", color=FOREST, no_wrap=True),
                    ft.Text("oo", size=22, weight="w500", color=SAGE, no_wrap=True),
                    ft.Text("m",  size=22, weight="w500", color=FOREST, no_wrap=True),
                ], spacing=0, tight=True),
                ft.Container(
                    content=ft.Row([
                        ft.Text("🌿", size=14),
                        ft.Text("3 day streak", ref=streak_ctrl, size=12,
                                color=FOREST_LT, weight="w500"),
                    ], spacing=4, tight=True),
                    bgcolor=LEAF_BG,
                    border_radius=20,
                    padding=ft.Padding(left=10, right=10, top=5, bottom=5),
                ),
            ], alignment="spaceBetween"),
            padding=ft.Padding(left=16, right=16, top=16, bottom=8),
        )

    # ─────────────────────────────────────────
    # BUILD TAB BAR
    # ─────────────────────────────────────────
    def tab_style(active):
        return ft.ButtonStyle(
            bgcolor=WHITE if active else "transparent",
            color=FOREST if active else TEXT_SEC,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding(left=20, right=20, top=8, bottom=8),
            overlay_color="transparent",
        )

    def on_garden_tab(e):
        tab_garden_btn.current.style    = tab_style(True)
        tab_nutrition_btn.current.style = tab_style(False)
        switch_tab("garden")

    def on_nutrition_tab(e):
        tab_garden_btn.current.style    = tab_style(False)
        tab_nutrition_btn.current.style = tab_style(True)
        switch_tab("nutrition")
    
    def on_log_tab(e):
        tab_garden_btn.current.style    = tab_style(False)
        tab_nutrition_btn.current.style = tab_style(False)
        tab_log_btn.current.style       = tab_style(True)
        switch_tab("log")


    def add_food_to_nutrition(text):
        with open(r"C:\Users\arnav\OneDrive\Desktop\app\food.csv", "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['description'] == text:
                    fdc_id = row['fdc_id']
        with open(r"C:\Users\arnav\OneDrive\Desktop\app\food_nutrient.csv", "r", newline="", encoding="utf-8") as g:
            reader = csv.DictReader(g)

            sat = 0
            mono = 0

            for row in reader:
                if row["fdc_id"] != fdc_id:
                    continue

                amount = float(row["amount"])
                nutrient = row["nutrient_id"]
                
                if nutrient == "301":
                    state.BASE["calcium"] += amount

                elif nutrient == "303":
                     state.BASE["iron"] += amount

                elif nutrient == "291":
                    state.BASE["total_fiber"] += amount

                elif nutrient == "203":      # protein
                    state.BASE["protein"] += amount

                elif nutrient == "645":
                    mono += amount

                elif nutrient == "646":
                    sat += amount
                    state.BASE["unsat_fat"] += mono + sat

                elif nutrient == "320":
                    state.BASE["vit_a"] += amount

                elif nutrient == "401":
                    state.BASE["vit_c"] += amount

                elif nutrient == "328":
                    state.BASE["vit_d"] += amount

                elif nutrient == "323":
                    state.BASE["vit_e"] += amount


    # async def add_food(e):
    #     food = food_autocomplete_ref.current.value.strip()
        
    #     if not food:
    #         return
        
    #     show_loading("Finding serving sizes...")
        
    #     try:
    #             import asyncio
    #             options = await asyncio.to_thread(get_serving_options, food)

    #             options = get_serving_options(food)
    #             print("OPTIONS:", options)

    #             page.run_thread(lambda: show_serving_dialog(food, options))

    #             print(show_serving_dialog(food, options))

    #     except Exception as ex:
    #             print(ex)
            
    #     threading.Thread(target=worker, daemon=True).start()

    async def add_food():
        food = food_autocomplete_ref.current.value.strip()
        if not food: 
            return
        

        determinate_ring = ft.ProgressRing(
        width=16, height=16, stroke_width=2, value=0
    )
        determinate_message = ft.Text("Wait for the completion...")

        page.add(
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                determinate_ring,
                                determinate_message,
                            ],
                        ),
                    ]
                )
            )
        )

        async def update_progress():
            # Fill the ring over ~10 seconds
            for i in range(101):
                determinate_ring.value = i / 100
                page.update()
                await asyncio.sleep(0.1)  # 101 * 0.1s ≈ 10 seconds

            determinate_ring.visible = False
            determinate_message.visible = False
            page.update()

        async def worker():
                options = await asyncio.to_thread(get_serving_options, food)
                print("OPTIONS:", options)
                page.run_thread(lambda: show_serving_dialog(food, options))

        task1 = asyncio.create_task(update_progress())
        task2 = asyncio.create_task(worker())
        await asyncio.gather(task1, task2)

    tab_bar = ft.Container(
        content=ft.Row([
            ft.TextButton("Garden",    ref=tab_garden_btn,
                          style=tab_style(True),  on_click=on_garden_tab),
            ft.TextButton("Nutrition", ref=tab_nutrition_btn,
                          style=tab_style(False), on_click=on_nutrition_tab),
            ft.TextButton("Log", ref=tab_log_btn,
                          style=tab_style(False), on_click=on_log_tab),
        ], spacing=4),
        bgcolor=GRAY_LT,
        border_radius=14,
        padding=4,
        margin=ft.Margin(left=16, right=16, top=0, bottom=0),
    )

    # ─────────────────────────────────────────
    # ASSEMBLE PAGE
    # ─────────────────────────────────────────
    garden_tab    = build_garden_tab()
    nutrition_tab = build_nutrition_tab()
    log_tab       = build_log_tab()
    page.add(
        ft.Column([
            build_header(),
            tab_bar,
            ft.Container(height=8),
            garden_tab,
            nutrition_tab,
            log_tab,
        ], spacing=0, expand=True),
    )

    # Initial plant render
    update_plant()
    update_plant()  # second pass ensures refs are live

    # Open setup dialog on first load
    setup_dialog_ctrl.open = True
    page.update()

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    ft.app(target=main)
