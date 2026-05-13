from __future__ import annotations

import argparse
import tkinter as tk
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

from kegg.formats.bob import parse_bob_header
from kegg.formats.bob_decode import decode_bob_sprites
from kegg.formats.cod import decode_file
from kegg.formats.level import (
    BRICK_GRID_HEIGHT,
    BRICK_GRID_WIDTH,
    ENEMY_TYPE_TO_DISPLAY_FRAME,
    ENEMY_TYPE_TO_FRAMES,
    SPELL_DROP_TYPE_TO_FRAMES,
    load_level_set,
    spell_bob_sprite_index_for_frame,
    spell_name_for_frame,
)
from kegg.formats.exe_backgrounds import (
    BACKGROUND_FILL_FIRST,
    BACKGROUND_FILL_LAST,
    BackgroundTableStore,
)
from kegg.formats.level_edit import EditableLevelStore
from kegg.graphics.bob_preview import bob_preview_info, make_raw_bob_atlas
from kegg.graphics.level_preview import BRICK_STEP_H, BRICK_STEP_W, make_game_level_preview, make_level_preview


class ScrollableImage(ttk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg="#202020", highlightthickness=0)
        self.xbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.ybar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.xbar.set, yscrollcommand=self.ybar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.ybar.grid(row=0, column=1, sticky="ns")
        self.xbar.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._photo: Optional[ImageTk.PhotoImage] = None

    def set_image(self, image: Image.Image) -> None:
        self._photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, image.width, image.height))


class SpriteAtlasTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self._build_ui()
        self.refresh_files()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="Sprite / image files").pack(anchor="w")
        self.file_list = tk.Listbox(left, width=28, height=28, exportselection=False)
        self.file_list.pack(fill="y", expand=True, pady=(4, 8))
        self.file_list.bind("<<ListboxSelect>>", lambda _event: self.show_selected())
        ttk.Button(left, text="Refresh", command=self.refresh_files).pack(fill="x")

        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.info = tk.Text(right, height=7, wrap="word")
        self.info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.info.configure(state="disabled")
        self.preview = ScrollableImage(right)
        self.preview.grid(row=1, column=0, sticky="nsew")

    def refresh_files(self) -> None:
        self.file_list.delete(0, tk.END)
        for path in sorted(self.data_dir.glob("*")):
            if path.suffix.upper() in {".BOB", ".GIF"}:
                self.file_list.insert(tk.END, path.name)
        if self.file_list.size():
            self.file_list.selection_set(0)
            self.show_selected()

    def _set_info(self, text: str) -> None:
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def show_selected(self) -> None:
        selection = self.file_list.curselection()
        if not selection:
            return
        path = self.data_dir / self.file_list.get(selection[0])
        try:
            if path.suffix.upper() == ".GIF":
                decoded = decode_file(path).data
                image = Image.open(BytesIO(decoded)).convert("RGBA")
                self._set_info(
                    f"{path.name}\n"
                    f"Decoded as GIF. Size: {image.width} x {image.height}\n"
                    f"This path is already real image decoding, not a raw guess."
                )
                self.preview.set_image(image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST))
            elif path.suffix.upper() == ".BOB":
                header = parse_bob_header(path)
                info = bob_preview_info(path)
                text = (
                    f"{info.file_name}\n"
                    f"objects: {info.object_count}\n"
                    f"logical sprite size: {info.width} x {info.height}\n"
                    f"header size: {info.header_size}\n"
                    f"payload size: {info.payload_size}\n"
                    f"bounds: left={header.bounds_left}, top={header.bounds_top}, right={header.bounds_right}, bottom={header.bounds_bottom}\n"
                    f"note: {info.note}"
                )
                self._set_info(text)
                self.preview.set_image(make_raw_bob_atlas(path, self.data_dir, scale=3))
        except Exception as exc:
            messagebox.showerror("Preview error", str(exc))


class ImageChoicePalette(ttk.Frame):
    """Scrollable image-card grid used for brick and spell selection."""

    def __init__(
        self,
        parent: tk.Widget,
        items: list[dict],
        on_select,
        columns: int = 4,
        card_width: int = 82,
    ) -> None:
        super().__init__(parent)
        self.items = items
        self.on_select = on_select
        self.columns = columns
        self.card_width = card_width
        self.selected_value = None
        self._photos: list[ImageTk.PhotoImage] = []
        self._cards: dict[object, tk.Frame] = {}
        self._card_order: list[tk.Frame] = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg="#202020", highlightthickness=0, width=card_width * columns + 24)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.inner = tk.Frame(self.canvas, bg="#202020")
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner.bind("<MouseWheel>", self._on_mousewheel)

        self._build_cards()
        if self.items:
            self.select(self.items[0]["value"], notify=True)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)
        available_width = max(1, event.width - 18)
        new_columns = max(1, available_width // (self.card_width + 8))
        if new_columns != self.columns:
            self.columns = new_columns
            self._layout_cards()

    def _on_mousewheel(self, event: tk.Event) -> None:
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def _make_photo(self, image: Image.Image, max_w: int, max_h: int) -> ImageTk.PhotoImage:
        rgba = image.convert("RGBA")
        if rgba.width <= 0 or rgba.height <= 0:
            rgba = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        ratio = min(max_w / rgba.width, max_h / rgba.height)
        if rgba.width < max_w // 2 and rgba.height < max_h // 2:
            ratio = max(ratio, 1.0)
        size = (max(1, int(rgba.width * ratio)), max(1, int(rgba.height * ratio)))
        rgba = rgba.resize(size, Image.Resampling.NEAREST)
        thumb = Image.new("RGBA", (max_w, max_h), (26, 26, 30, 255))
        thumb.alpha_composite(rgba, ((max_w - rgba.width) // 2, (max_h - rgba.height) // 2))
        return ImageTk.PhotoImage(thumb)

    def _build_cards(self) -> None:
        for item in self.items:
            value = item["value"]

            card = tk.Frame(self.inner, bg="#303036", bd=2, relief="ridge", padx=3, pady=3)
            photo = self._make_photo(item["image"], max_w=self.card_width - 16, max_h=48)
            self._photos.append(photo)
            image_label = tk.Label(card, image=photo, bg="#303036")
            image_label.pack(fill="x")

            text_label = tk.Label(
                card,
                text=item["label"],
                bg="#303036",
                fg="#f0f0f0",
                justify="center",
                wraplength=self.card_width - 8,
                font=("TkDefaultFont", 8),
            )
            text_label.pack(fill="x", pady=(2, 0))

            for widget in (card, image_label, text_label):
                widget.bind("<Button-1>", lambda _event, selected=value: self.select(selected, notify=True))
                widget.bind("<MouseWheel>", self._on_mousewheel)

            self._cards[value] = card
            self._card_order.append(card)

        self._layout_cards()

    def _layout_cards(self) -> None:
        for index, card in enumerate(self._card_order):
            row = index // self.columns
            col = index % self.columns
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        for col in range(max(self.columns, 1)):
            self.inner.grid_columnconfigure(col, weight=1)

    def select(self, value, notify: bool = False) -> None:
        self.selected_value = value
        for card_value, card in self._cards.items():
            selected = card_value == value
            bg = "#5a4400" if selected else "#303036"
            card.configure(bg=bg, highlightbackground="#ffd84d", highlightthickness=2 if selected else 0)
            for child in card.winfo_children():
                child.configure(bg=bg)
        if notify:
            self.on_select(value)


class EditorPaletteTabs(ttk.Notebook):
    """Right-side editor tabs: bricks, spells, cell inspector, and level metadata."""

    def __init__(self, parent: tk.Widget, data_dir: Path, on_brick_select, on_spell_select) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self.brick_palette = self._make_brick_palette(on_brick_select)
        self.spell_palette = self._make_spell_palette(on_spell_select)
        self.inspector_tab = ttk.Frame(self, padding=8)
        self.metadata_tab = ttk.Frame(self, padding=8)
        self.add(self.brick_palette, text="Bricks")
        self.add(self.spell_palette, text="Spells")
        self.add(self.inspector_tab, text="Cell Inspector")
        self.add(self.metadata_tab, text="Level Metadata")

    def active_editor_kind(self) -> str | None:
        current = self.select()
        if current == str(self.brick_palette):
            return "bricks"
        if current == str(self.spell_palette):
            return "spells"
        return None

    def _make_brick_palette(self, on_brick_select) -> ImageChoicePalette:
        brick_sprites, _ = decode_bob_sprites(self.data_dir / "KE_BRICK.BOB", self.data_dir)
        items = []
        # Spell-marked brick sprites 48..95 are not directly editable. They are
        # generated automatically when a spell is placed on base bricks 0..47.
        for sprite_id, image in enumerate(brick_sprites[:255]):
            if 48 <= sprite_id <= 95:
                continue
            items.append({"value": sprite_id, "image": image, "label": str(sprite_id)})
        return ImageChoicePalette(self, items, on_brick_select, columns=4, card_width=76)

    def _make_spell_palette(self, on_spell_select) -> ImageChoicePalette:
        spell_sprites, _ = decode_bob_sprites(self.data_dir / "KE_SPELL.BOB", self.data_dir)
        items = []
        for drop_type in sorted(SPELL_DROP_TYPE_TO_FRAMES):
            frames = SPELL_DROP_TYPE_TO_FRAMES[drop_type]
            frame = frames[0]
            sprite_index = spell_bob_sprite_index_for_frame(frame)
            if not (0 <= sprite_index < len(spell_sprites)):
                continue
            name = spell_name_for_frame(frame) or f"Unknown {frame}"
            items.append(
                {
                    "value": drop_type,
                    "image": spell_sprites[sprite_index],
                    "label": f"{name}\nT{drop_type:02d}",
                }
            )
        return ImageChoicePalette(self, items, on_spell_select, columns=3, card_width=98)


class LevelViewTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self.level_store = EditableLevelStore.load(data_dir / "KE_LDCWC.TAB")
        self.background_store = BackgroundTableStore.load(data_dir / "KE.EXE", data_dir / "KE_FILL.BOB")
        self.fill_sprites, _ = decode_bob_sprites(data_dir / "KE_FILL.BOB", data_dir)
        self.levels = load_level_set(data_dir)
        self.level_var = tk.IntVar(value=min(2, self.level_store.level_count))
        self.zoom_var = tk.StringVar(value="4x")
        self.view_var = tk.StringVar(value="game")
        self.show_grid_var = tk.BooleanVar(value=False)
        self.show_ids_var = tk.BooleanVar(value=False)
        self.show_spells_var = tk.BooleanVar(value=False)
        self.selected_brick_sprite_id: int | None = 0
        self.selected_spell_drop_type: int | None = 0
        self.selected_cell_text = "Left click places from the active editor tab. Right click erases."
        self.status_var = tk.StringVar(value="")
        self.background_choice_var = tk.StringVar(value="")
        self.spawn_interval_var = tk.IntVar(value=0)
        self.enemy_sprites, _ = decode_bob_sprites(data_dir / "KE_NMY.BOB", data_dir)
        self.enemy_slot_values = [0 for _ in range(8)]
        self.enemy_slot_image_labels: list[tk.Label] = []
        self.enemy_slot_text_labels: list[ttk.Label] = []
        self._enemy_slot_photos: list[ImageTk.PhotoImage | None] = [None for _ in range(8)]
        self._background_photo: ImageTk.PhotoImage | None = None
        self._metadata_refreshing = False

        self.undo_stack: list[tuple[bytes, list[int]]] = []
        self.redo_stack: list[tuple[bytes, list[int]]] = []
        self._drag_snapshot: tuple[bytes, list[int]] | None = None
        self._drag_button: str | None = None
        self._drag_visited: set[tuple[int, int]] = set()

        self._build_ui()
        self.level_var.trace_add("write", lambda *_args: self.after_idle(self.render_level))
        self.bind_all("<Control-z>", lambda _event: self.undo())
        self.bind_all("<Control-y>", lambda _event: self.redo())
        self.bind_all("<Control-Shift-Z>", lambda _event: self.redo())
        self.editor_palettes.bind("<<NotebookTabChanged>>", lambda _event: self._update_editor_status())
        self._update_editor_status()
        self.render_level()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Label(toolbar, text="Level").pack(side="left")
        spin = ttk.Spinbox(
            toolbar,
            from_=1,
            to=max(1, self.level_store.level_count),
            width=5,
            textvariable=self.level_var,
        )
        spin.pack(side="left", padx=(4, 12))
        spin.bind("<Return>", lambda _event: self.render_level())
        spin.bind("<FocusOut>", lambda _event: self.render_level())

        ttk.Label(toolbar, text="Zoom").pack(side="left")
        zoom_box = ttk.Combobox(
            toolbar,
            width=5,
            textvariable=self.zoom_var,
            values=["1x", "2x", "3x", "4x", "5x", "6x", "8x"],
            state="readonly",
        )
        zoom_box.pack(side="left", padx=(4, 12))
        zoom_box.bind("<<ComboboxSelected>>", lambda _event: self.render_level())

        ttk.Label(toolbar, text="View").pack(side="left")
        view_box = ttk.Combobox(
            toolbar,
            width=14,
            textvariable=self.view_var,
            values=["game", "spells", "bricks"],
            state="readonly",
        )
        view_box.pack(side="left", padx=(4, 12))
        view_box.bind("<<ComboboxSelected>>", lambda _event: self.render_level())

        ttk.Button(toolbar, text="Clear level", command=self.clear_level).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Undo", command=self.undo).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Redo", command=self.redo).pack(side="left", padx=(4, 0))

        ttk.Button(toolbar, text="Save data", command=self.save_levels).pack(side="right")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right", padx=(0, 12))

        self.main_pane = ttk.Panedwindow(self, orient="horizontal")
        self.main_pane.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.preview = ScrollableImage(self.main_pane)
        self.main_pane.add(self.preview, weight=4)
        self.preview.canvas.bind("<ButtonPress-1>", self.on_preview_left_press)
        self.preview.canvas.bind("<B1-Motion>", self.on_preview_left_drag)
        self.preview.canvas.bind("<ButtonRelease-1>", self.on_preview_left_release)
        self.preview.canvas.bind("<ButtonPress-3>", self.on_preview_right_press)
        self.preview.canvas.bind("<B3-Motion>", self.on_preview_right_drag)
        self.preview.canvas.bind("<ButtonRelease-3>", self.on_preview_right_release)

        side = ttk.Frame(self.main_pane, padding=8)
        self.main_pane.add(side, weight=2)
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Display").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(side, text="Grid overlay", variable=self.show_grid_var, command=self.render_level).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(side, text="Brick image ids overlay", variable=self.show_ids_var, command=self.render_level).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(side, text="Spell icons overlay", variable=self.show_spells_var, command=self.render_level).grid(row=3, column=0, sticky="w")

        ttk.Separator(side).grid(row=4, column=0, sticky="ew", pady=8)
        ttk.Label(side, text="Editor").grid(row=5, column=0, sticky="w")
        self.editor_status = ttk.Label(side, text="", wraplength=360, justify="left")
        self.editor_status.grid(row=6, column=0, sticky="ew", pady=(0, 4))

        self.editor_palettes = EditorPaletteTabs(
            side,
            self.data_dir,
            on_brick_select=self.on_brick_selected,
            on_spell_select=self.on_spell_selected,
        )
        self.editor_palettes.grid(row=7, column=0, sticky="nsew")
        side.rowconfigure(7, weight=3)

        self._build_cell_inspector_tab(self.editor_palettes.inspector_tab)
        self._build_level_metadata_tab(self.editor_palettes.metadata_tab)

    def _build_cell_inspector_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.info = tk.Text(parent, width=46, height=32, wrap="word")
        self.info.grid(row=0, column=0, sticky="nsew")
        self.info.configure(state="disabled")

    def _build_level_metadata_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(10, weight=1)

        ttk.Label(parent, text="Background / KE_FILL").grid(row=0, column=0, sticky="w")
        background_row = ttk.Frame(parent)
        background_row.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        background_row.columnconfigure(1, weight=1)
        ttk.Label(background_row, text="Sprite").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.background_combo = ttk.Combobox(
            background_row,
            width=12,
            textvariable=self.background_choice_var,
            values=[str(i) for i in range(BACKGROUND_FILL_FIRST, BACKGROUND_FILL_LAST + 1)],
            state="readonly",
        )
        self.background_combo.grid(row=0, column=1, sticky="ew")
        self.background_combo.bind("<<ComboboxSelected>>", self._on_background_selected)

        self.background_slot_label = ttk.Label(parent, text="", wraplength=360, justify="left")
        self.background_slot_label.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.background_preview_label = tk.Label(parent, bg="#202020", bd=1, relief="sunken")
        self.background_preview_label.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(parent, text="Level record metadata").grid(row=4, column=0, sticky="w", pady=(4, 2))
        metadata_note = (
            "EXE tracing: record bytes 0..1 load a raw enemy spawn countdown/timer. "
            "Bytes 2..9 are the 8-slot enemy spawn cycle. The stored IDs are already 0-based: "
            "0 = Enemy 0, 1 = Enemy 1, ..., 7 = Enemy 7."
        )
        ttk.Label(parent, text=metadata_note, wraplength=360, justify="left").grid(row=5, column=0, sticky="ew", pady=(0, 6))

        spawn_row = ttk.Frame(parent)
        spawn_row.grid(row=6, column=0, sticky="ew", pady=(0, 6))
        spawn_row.columnconfigure(1, weight=1)
        ttk.Label(spawn_row, text="Enemy spawn timer").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.spawn_interval_spin = ttk.Spinbox(
            spawn_row,
            from_=0,
            to=65535,
            width=10,
            textvariable=self.spawn_interval_var,
        )
        self.spawn_interval_spin.grid(row=0, column=1, sticky="w")

        enemy_box = ttk.LabelFrame(parent, text="Enemy spawn cycle")
        enemy_box.grid(row=7, column=0, sticky="ew", pady=(0, 6))
        for col in range(4):
            enemy_box.columnconfigure(col, weight=1)

        self.enemy_slot_image_labels.clear()
        self.enemy_slot_text_labels.clear()
        for slot in range(8):
            col = slot % 4
            row = slot // 4
            cell = ttk.Frame(enemy_box, padding=(4, 4))
            cell.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            ttk.Label(cell, text=f"Slot {slot}").pack()

            image_label = tk.Label(cell, bg="#202020", bd=1, relief="sunken", width=72, height=54)
            image_label.pack(pady=(2, 2))
            image_label.bind("<Button-1>", lambda _event, selected_slot=slot: self._change_enemy_slot(selected_slot, +1))
            image_label.bind("<Button-3>", lambda _event, selected_slot=slot: self._change_enemy_slot(selected_slot, -1))
            self.enemy_slot_image_labels.append(image_label)

            text_label = ttk.Label(cell, text="Enemy 0", justify="center")
            text_label.pack()
            self.enemy_slot_text_labels.append(text_label)

            controls = ttk.Frame(cell)
            controls.pack(pady=(2, 0))
            ttk.Button(controls, text="◀", width=3, command=lambda selected_slot=slot: self._change_enemy_slot(selected_slot, -1)).pack(side="left")
            ttk.Button(controls, text="▶", width=3, command=lambda selected_slot=slot: self._change_enemy_slot(selected_slot, +1)).pack(side="left", padx=(2, 0))

        buttons = ttk.Frame(parent)
        buttons.grid(row=8, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(buttons, text="Apply level metadata", command=self.apply_level_metadata).pack(side="left")

        save_note = (
            "Background changes patch the KE.EXE background table and affect this background slot "
            "again after the 41-level wrap. Save data writes KE_LDCWC.TAB and KE.EXE, with .bak backups."
        )
        ttk.Label(parent, text=save_note, wraplength=360, justify="left").grid(row=9, column=0, sticky="ew")

    def _refresh_level_metadata_tab(self) -> None:
        if not hasattr(self, "background_combo"):
            return
        level = self._current_level_number()
        self._metadata_refreshing = True
        try:
            fill_sprite = self.background_store.get_fill_sprite_for_level(level)
            self.background_choice_var.set(str(fill_sprite))
            slot = self.background_store.slot_for_level(level)
            linked_level = level + self.background_store.slot_count
            linked_text = (
                f"EXE background table slot {slot}: level {level} uses KE_FILL sprite {fill_sprite}. "
                f"The same slot repeats for level {linked_level} after the 41-slot wrap."
            )
            self.background_slot_label.configure(text=linked_text)
            self.spawn_interval_var.set(self.level_store.get_spawn_interval(level))
            enemy_values = self.level_store.get_enemy_sequence(level)
            self.enemy_slot_values = [max(0, min(7, int(value))) for value in enemy_values]
            for slot in range(8):
                self._update_enemy_slot_preview(slot)
            self._update_background_preview()
        finally:
            self._metadata_refreshing = False

    def _update_background_preview(self) -> None:
        if not hasattr(self, "background_preview_label"):
            return
        try:
            sprite_id = int(self.background_choice_var.get())
        except (TypeError, ValueError):
            return
        if not (0 <= sprite_id < len(self.fill_sprites)):
            return
        image = self.fill_sprites[sprite_id].convert("RGBA")
        if image.width <= 0 or image.height <= 0:
            return
        max_w = 340
        max_h = 96
        ratio = min(max_w / image.width, max_h / image.height)
        if image.width < max_w // 2 and image.height < max_h // 2:
            ratio = max(1.0, ratio)
        image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.Resampling.NEAREST)
        thumb = Image.new("RGBA", (max_w, max_h), (24, 24, 28, 255))
        thumb.alpha_composite(image, ((max_w - image.width) // 2, (max_h - image.height) // 2))
        self._background_photo = ImageTk.PhotoImage(thumb)
        self.background_preview_label.configure(image=self._background_photo)

    def _enemy_preview_photo(self, enemy_type: int) -> ImageTk.PhotoImage:
        enemy_type = max(0, min(7, int(enemy_type)))
        frame = ENEMY_TYPE_TO_DISPLAY_FRAME.get(enemy_type, 0)
        if not (0 <= frame < len(self.enemy_sprites)):
            frame = 0
        image = self.enemy_sprites[frame].convert("RGBA")
        max_w = 68
        max_h = 50
        if image.width <= 0 or image.height <= 0:
            image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        ratio = min(max_w / image.width, max_h / image.height)
        if image.width < max_w // 2 and image.height < max_h // 2:
            ratio = max(1.0, ratio)
        image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.Resampling.NEAREST)
        thumb = Image.new("RGBA", (72, 54), (24, 24, 28, 255))
        thumb.alpha_composite(image, ((thumb.width - image.width) // 2, (thumb.height - image.height) // 2))
        return ImageTk.PhotoImage(thumb)

    def _update_enemy_slot_preview(self, slot: int) -> None:
        if not (0 <= slot < len(self.enemy_slot_values)):
            return
        enemy_type = max(0, min(7, int(self.enemy_slot_values[slot])))
        self.enemy_slot_values[slot] = enemy_type
        if slot < len(self.enemy_slot_image_labels):
            photo = self._enemy_preview_photo(enemy_type)
            self._enemy_slot_photos[slot] = photo
            self.enemy_slot_image_labels[slot].configure(image=photo)
        if slot < len(self.enemy_slot_text_labels):
            self.enemy_slot_text_labels[slot].configure(text=f"Enemy {enemy_type}")

    def _change_enemy_slot(self, slot: int, delta: int) -> None:
        if self._metadata_refreshing:
            return
        if not (0 <= slot < len(self.enemy_slot_values)):
            return
        self.enemy_slot_values[slot] = (int(self.enemy_slot_values[slot]) + delta) % 8
        self._update_enemy_slot_preview(slot)

    def _on_background_selected(self, _event: tk.Event | None = None) -> None:
        if self._metadata_refreshing:
            return
        before = self._capture_edit_state()
        try:
            fill_sprite = int(self.background_choice_var.get())
            self.background_store.set_fill_sprite_for_level(self._current_level_number(), fill_sprite)
            self._update_background_preview()
            self._commit_edit_state(before)
            self.render_level(refresh_metadata=False)
        except Exception as exc:
            messagebox.showerror("Background update failed", str(exc))
            self._restore_edit_state(before)
            self._refresh_level_metadata_tab()

    def apply_level_metadata(self) -> None:
        before = self._capture_edit_state()
        try:
            level = self._current_level_number()
            self.level_store.set_spawn_interval(level, int(self.spawn_interval_var.get()))
            for slot, enemy_type in enumerate(self.enemy_slot_values):
                self.level_store.set_enemy_sequence_value(level, slot, int(enemy_type))
            self._commit_edit_state(before)
            self.render_level(refresh_metadata=True)
        except Exception as exc:
            messagebox.showerror("Metadata update failed", str(exc))
            self._restore_edit_state(before)
            self._refresh_level_metadata_tab()

    def _set_info(self, text: str) -> None:
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def _preview_scale(self) -> int:
        raw = self.zoom_var.get().strip().lower().replace("×", "x")
        if raw.endswith("x"):
            raw = raw[:-1]
        try:
            scale = int(raw)
        except ValueError:
            scale = 4
        return max(1, min(8, scale))

    def _current_level_number(self) -> int:
        return max(1, min(self.level_var.get(), self.level_store.level_count))

    def _current_render_level(self):
        return self.level_store.render_level(self._current_level_number())

    def _cell_at_image_xy(self, image_x: float, image_y: float):
        x = int(image_x) // (BRICK_STEP_W * self._preview_scale())
        y = int(image_y) // (BRICK_STEP_H * self._preview_scale())
        if 0 <= x < BRICK_GRID_WIDTH and 0 <= y < BRICK_GRID_HEIGHT:
            return self.level_store.get_cell(self._current_level_number(), x, y)
        return None

    def _cell_text(self, cell) -> str:
        sprite_id = cell.brick_sprite_id
        powerup = cell.powerup_spell_id
        spell_name = cell.powerup_spell_name
        return (
            f"Selected cell\n"
            f"  position: x={cell.x}, y={cell.y}\n"
            f"  linear index: {cell.y * BRICK_GRID_WIDTH + cell.x}\n"
            f"  raw word: 0x{cell.raw_word:04x}\n"
            f"  stored brick id: {cell.brick_id}\n"
            f"  rendered KE_BRICK.BOB image: {sprite_id if sprite_id is not None else 'empty'}\n"
            f"  brick class: {cell.brick_class}\n"
            f"  can contain powerup: {cell.can_contain_powerup}\n"
            f"  low byte / metadata: {cell.flags} (0x{cell.flags:02x})\n"
            f"  EXE drop type: {cell.powerup_drop_type if cell.powerup_drop_type is not None else 'none'}\n"
            f"  variant bits: {cell.powerup_variant if cell.powerup_variant is not None else 'none'}\n"
            f"  game spell frames: {cell.powerup_frames if cell.powerup_frames is not None else 'none'}\n"
            f"  representative game frame: {powerup if powerup is not None else 'none'}\n"
            f"  actual KE_SPELL.BOB image: {cell.powerup_spell_bob_sprite_index if cell.powerup_spell_bob_sprite_index is not None else 'none'}\n"
            f"  logical spell: {spell_name if spell_name is not None else 'none'}\n"
        )

    def _inspect_cell(self, cell) -> None:
        self.selected_cell_text = self._cell_text(cell)

    def _capture_edit_state(self) -> tuple[bytes, list[int]]:
        return bytes(self.level_store.decoded), list(self.background_store.mapping)

    def _restore_edit_state(self, state: tuple[bytes, list[int]]) -> None:
        decoded, background_mapping = state
        self.level_store.decoded = bytearray(decoded)
        self.background_store.mapping = list(background_mapping)
        self.level_store.modified = True
        self.background_store.modified = True

    def _state_changed(self, before: tuple[bytes, list[int]]) -> bool:
        return before != self._capture_edit_state()

    def _commit_edit_state(self, before: tuple[bytes, list[int]] | None) -> None:
        if before is None:
            return
        if self._state_changed(before):
            self.undo_stack.append(before)
            self.redo_stack.clear()
        self._update_modified_status()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        current = self._capture_edit_state()
        previous = self.undo_stack.pop()
        self.redo_stack.append(current)
        self._restore_edit_state(previous)
        self._refresh_level_metadata_tab()
        self.render_level(refresh_metadata=False)

    def redo(self) -> None:
        if not self.redo_stack:
            return
        current = self._capture_edit_state()
        next_state = self.redo_stack.pop()
        self.undo_stack.append(current)
        self._restore_edit_state(next_state)
        self._refresh_level_metadata_tab()
        self.render_level(refresh_metadata=False)

    def clear_level(self) -> None:
        level = self._current_level_number()
        if not messagebox.askyesno("Clear level", f"Clear all brick and spell cells in level {level:02d}?"):
            return
        before = self._capture_edit_state()
        self.level_store.clear_level(level)
        self.selected_cell_text = f"Level {level:02d} grid cleared."
        self._commit_edit_state(before)
        self.render_level()

    def _cell_from_event(self, event: tk.Event):
        image_x = self.preview.canvas.canvasx(event.x)
        image_y = self.preview.canvas.canvasy(event.y)
        return self._cell_at_image_xy(image_x, image_y), image_x, image_y

    def _begin_preview_edit(self, event: tk.Event, button: str) -> None:
        if self.view_var.get() != "game":
            self.selected_cell_text = "Map editing is available in the game view."
            self.render_level(refresh_metadata=False)
            return
        cell, image_x, image_y = self._cell_from_event(event)
        if cell is None:
            self.selected_cell_text = f"Clicked outside level grid at image x={int(image_x)}, y={int(image_y)}."
            self.render_level()
            return
        self._drag_snapshot = self._capture_edit_state()
        self._drag_button = button
        self._drag_visited = set()
        self._apply_preview_edit(cell, button, allow_spells=True)

    def _drag_preview_edit(self, event: tk.Event, button: str) -> None:
        if self._drag_button != button:
            return
        if self.editor_palettes.active_editor_kind() != "bricks":
            return
        cell, _image_x, _image_y = self._cell_from_event(event)
        if cell is None:
            return
        self._apply_preview_edit(cell, button, allow_spells=False)

    def _finish_preview_edit(self, button: str) -> None:
        if self._drag_button != button:
            return
        before = self._drag_snapshot
        self._drag_snapshot = None
        self._drag_button = None
        self._drag_visited = set()
        self._commit_edit_state(before)
        self.render_level()

    def _apply_preview_edit(self, cell, button: str, allow_spells: bool) -> None:
        key = (cell.x, cell.y)
        if key in self._drag_visited:
            return
        self._drag_visited.add(key)

        level = self._current_level_number()
        editor_kind = self.editor_palettes.active_editor_kind()
        edit_message: str | None = None
        if editor_kind == "bricks":
            if button == "left":
                self.level_store.set_brick_sprite_id(level, cell.x, cell.y, self.selected_brick_sprite_id)
            elif button == "right":
                self.level_store.erase_brick(level, cell.x, cell.y)
        elif allow_spells and editor_kind == "spells":
            if button == "left":
                applied = self.level_store.set_spell_drop_type(level, cell.x, cell.y, self.selected_spell_drop_type)
                if not applied:
                    edit_message = (
                        f"Spell drop not applied at x={cell.x}, y={cell.y}. "
                        "Spells are allowed only on base breakable bricks 0..47 "
                        "(auto-converted to dotted variants 48..95) or existing dotted variants 48..95."
                    )
            elif button == "right":
                self.level_store.erase_spell(level, cell.x, cell.y)

        inspected = self.level_store.get_cell(level, cell.x, cell.y)
        self._inspect_cell(inspected)
        if edit_message is not None:
            self.selected_cell_text = edit_message + "\n\n" + self.selected_cell_text
        self._update_modified_status()
        self.render_level(refresh_metadata=False)

    def on_preview_left_press(self, event: tk.Event) -> None:
        self._begin_preview_edit(event, "left")

    def on_preview_left_drag(self, event: tk.Event) -> None:
        self._drag_preview_edit(event, "left")

    def on_preview_left_release(self, _event: tk.Event) -> None:
        self._finish_preview_edit("left")

    def on_preview_right_press(self, event: tk.Event) -> None:
        self._begin_preview_edit(event, "right")

    def on_preview_right_drag(self, event: tk.Event) -> None:
        self._drag_preview_edit(event, "right")

    def on_preview_right_release(self, _event: tk.Event) -> None:
        self._finish_preview_edit("right")

    def on_brick_selected(self, sprite_id: int) -> None:
        self.selected_brick_sprite_id = sprite_id
        self._update_editor_status()

    def on_spell_selected(self, drop_type: int) -> None:
        self.selected_spell_drop_type = drop_type
        self._update_editor_status()

    def _update_editor_status(self) -> None:
        kind = self.editor_palettes.active_editor_kind() if hasattr(self, "editor_palettes") else "bricks"
        if kind == "bricks":
            text = (
                f"Brick editor: selected KE_BRICK image {self.selected_brick_sprite_id}. "
                "Left click inserts/replaces a non-spell brick. Right click clears the entire cell. "
                "Dotted spell variants 48..95 are created automatically by the Spells tab."
            )
        elif kind == "spells":
            frames = SPELL_DROP_TYPE_TO_FRAMES.get(self.selected_spell_drop_type or 0, [])
            name = spell_name_for_frame(frames[0]) if frames else None
            text = (
                f"Spell editor: selected drop type {self.selected_spell_drop_type}"
                f"{f' ({name})' if name else ''}. "
                "Left click writes spell/drop metadata only on base breakable bricks 0..47 "
                "(auto-converted to dotted variants 48..95). Right click removes the spell and converts "
                "48..95 back to 0..47."
            )
        else:
            text = "Inspector/metadata tab: level clicks only inspect cells; switch to Bricks or Spells to edit the map."
        self.editor_status.configure(text=text)

    def _update_modified_status(self) -> None:
        modified = self.level_store.modified or self.background_store.modified
        self.status_var.set("Modified" if modified else "")

    def save_levels(self) -> None:
        try:
            saved_parts = []
            if self.level_store.modified:
                self.level_store.save(make_backup=True)
                saved_parts.append("KE_LDCWC.TAB")
            if self.background_store.modified:
                self.background_store.save(make_backup=True)
                saved_parts.append("KE.EXE background table")
            self._update_modified_status()
            if saved_parts:
                message = "Saved " + " and ".join(saved_parts) + ". .bak backups are kept on first save."
            else:
                message = "Nothing was modified."
            messagebox.showinfo("Data saved", message)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def render_level(self, refresh_metadata: bool = True) -> None:
        number = self._current_level_number()
        view = self.view_var.get()
        if refresh_metadata:
            self._refresh_level_metadata_tab()

        if view == "game":
            level = self._current_render_level()
            image = make_game_level_preview(
                self.data_dir,
                number=number,
                scale=self._preview_scale(),
                show_grid=self.show_grid_var.get(),
                show_ids=self.show_ids_var.get(),
                show_spells=self.show_spells_var.get(),
                show_background=True,
                level_override=level,
                background_fill_sprite_id=self.background_store.get_fill_sprite_for_level(number),
            )
            self.preview.set_image(image)
            nonzero = sum(1 for cell in level.cells if cell.raw_word)
            powerups = sum(1 for cell in level.cells if cell.powerup_spell_id is not None)
            info = (
                f"Gameplay editor view\n"
                f"Level {number:02d}: {nonzero}/270 occupied cells.\n"
                f"Known powerup/drop code cells: {powerups}.\n"
                f"Background: KE_FILL.BOB sprite {self.background_store.get_fill_sprite_for_level(number)}.\n\n"
                f"{self.selected_cell_text}"
            )
        elif view == "spells":
            image = make_level_preview(self.data_dir, number=number, view="spells", scale=self._preview_scale(), level_override=self.level_store.render_level(number))
            self.preview.set_image(image)
            level = self.level_store.render_level(number)
            nonzero = sum(1 for cell in level.cells if cell.flags)
            info = (
                f"Spells / low-byte codes\n"
                f"Level {number:02d}: {nonzero}/270 non-zero cells.\n"
                "This diagnostic view reflects the current in-memory editor state."
            )
        elif view == "bricks":
            image = make_level_preview(self.data_dir, number=number, view="bricks", scale=self._preview_scale(), level_override=self.level_store.render_level(number))
            self.preview.set_image(image)
            level = self.level_store.render_level(number)
            nonzero = sum(1 for cell in level.cells if cell.brick_id)
            info = (
                f"Bricks / high-byte ids\n"
                f"Level {number:02d}: {nonzero}/270 non-zero cells.\n"
                "This diagnostic view reflects the current in-memory editor state."
            )
        else:
            level = self._current_render_level()
            image = make_game_level_preview(
                self.data_dir,
                number=number,
                scale=self._preview_scale(),
                level_override=level,
                background_fill_sprite_id=self.background_store.get_fill_sprite_for_level(number),
            )
            self.preview.set_image(image)
            info = f"Unknown view '{view}', falling back to gameplay editor for level {number:02d}."

        self._set_info(info)
        self._update_modified_status()


class KeggEditorApp(tk.Tk):
    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.title("Krypton Egg reverse editor")
        self.geometry("1200x850")
        self.data_dir = data_dir
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, padding=8)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Button(header, text="Change data directory…", command=self.change_data_dir).pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew")
        notebook.add(LevelViewTab(notebook, self.data_dir), text="Level View")
        notebook.add(SpriteAtlasTab(notebook, self.data_dir), text="Sprite Atlas")

    def change_data_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.data_dir))
        if not selected:
            return
        # Simpler and safer for now: restart the app state around a new data dir.
        self.destroy()
        KeggEditorApp(Path(selected)).mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the Krypton Egg reverse editor GUI")
    parser.add_argument("--data-dir", default="game_data", help="Directory containing the original game files")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data directory does not exist: {data_dir}")
    app = KeggEditorApp(data_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
