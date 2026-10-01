import random
import tkinter as tk
from tkinter import messagebox, ttk


SIZE = 9
BOX_SIZE = 3
Grid = list[list[int]]


def candidates(board: Grid, row: int, col: int) -> list[int]:
    """Return digits that do not conflict with this cell's row, column, or box."""
    used = set(board[row])
    used.update(board[index][col] for index in range(SIZE))
    box_row = row // BOX_SIZE * BOX_SIZE
    box_col = col // BOX_SIZE * BOX_SIZE
    used.update(
        board[r][c]
        for r in range(box_row, box_row + BOX_SIZE)
        for c in range(box_col, box_col + BOX_SIZE)
    )
    return [digit for digit in range(1, SIZE + 1) if digit not in used]


def find_best_empty(board: Grid) -> tuple[int, int, list[int]] | None:
    """Choose the empty cell with the fewest legal values (MRV heuristic)."""
    best: tuple[int, int, list[int]] | None = None
    for row in range(SIZE):
        for col in range(SIZE):
            if board[row][col] == 0:
                options = candidates(board, row, col)
                if best is None or len(options) < len(best[2]):
                    best = (row, col, options)
                    if len(options) <= 1:
                        return best
    return best


def solve_board(board: Grid) -> bool:
    """Solve a board in place using recursive backtracking."""
    empty = find_best_empty(board)
    if empty is None:
        return True

    row, col, options = empty
    for digit in options:
        board[row][col] = digit
        if solve_board(board):
            return True
        board[row][col] = 0
    return False


def count_solutions(board: Grid, limit: int = 2) -> int:
    """Count solutions up to limit, stopping early once the limit is reached."""
    empty = find_best_empty(board)
    if empty is None:
        return 1

    row, col, options = empty
    total = 0
    for digit in options:
        board[row][col] = digit
        total += count_solutions(board, limit - total)
        board[row][col] = 0
        if total >= limit:
            return total
    return total


def make_complete_board() -> Grid:
    """Create a randomized complete board with recursive backtracking."""
    board = [[0] * SIZE for _ in range(SIZE)]

    def fill() -> bool:
        empty = find_best_empty(board)
        if empty is None:
            return True
        row, col, options = empty
        random.shuffle(options)
        for digit in options:
            board[row][col] = digit
            if fill():
                return True
            board[row][col] = 0
        return False

    fill()
    return board


def make_puzzle(clues: int) -> tuple[Grid, Grid]:
    """Generate a puzzle and remove clues only when uniqueness is preserved."""
    solution = make_complete_board()
    puzzle = [row[:] for row in solution]
    cells = [(row, col) for row in range(SIZE) for col in range(SIZE)]
    random.shuffle(cells)
    remaining = SIZE * SIZE

    for row, col in cells:
        if remaining <= clues:
            break
        value = puzzle[row][col]
        puzzle[row][col] = 0
        if count_solutions(puzzle) == 1:
            remaining -= 1
        else:
            puzzle[row][col] = value

    return puzzle, solution


class SudokuApp:
    COLORS = {
        "window": "#edf1eb",
        "board": "#ffffff",
        "given": "#e5ebe5",
        "text": "#20332b",
        "accent": "#147d64",
        "wrong": "#f8d9d4",
        "correct": "#d9eee4",
        "line": "#b7c7bd",
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Sudoku | Backtracking Puzzle")
        self.root.configure(bg=self.COLORS["window"])
        self.root.resizable(False, False)

        self.difficulty = tk.StringVar(value="Medium")
        self.entries: list[list[tk.Entry]] = []
        self.puzzle: Grid = []
        self.solution: Grid = []

        self._build_interface()
        self.new_game()

    def _build_interface(self) -> None:
        outer = tk.Frame(self.root, bg=self.COLORS["window"], padx=24, pady=20)
        outer.pack()

        heading = tk.Frame(outer, bg=self.COLORS["window"])
        heading.pack(fill="x", pady=(0, 14))
        tk.Label(
            heading,
            text="SUDOKU",
            font=("Segoe UI", 23, "bold"),
            bg=self.COLORS["window"],
            fg=self.COLORS["text"],
        ).pack(anchor="w")
        tk.Label(
            heading,
            text="9 x 9  /  BACKTRACKING",
            font=("Segoe UI", 9, "bold"),
            bg=self.COLORS["window"],
            fg=self.COLORS["accent"],
        ).pack(anchor="w", pady=(1, 0))

        board_frame = tk.Frame(
            outer,
            bg=self.COLORS["line"],
            padx=2,
            pady=2,
            highlightthickness=0,
        )
        board_frame.pack()

        for row in range(SIZE):
            entry_row: list[tk.Entry] = []
            for col in range(SIZE):
                entry = tk.Entry(
                    board_frame,
                    width=2,
                    justify="center",
                    font=("Segoe UI", 18),
                    relief="flat",
                    bd=0,
                    bg=self.COLORS["board"],
                    fg=self.COLORS["text"],
                    insertbackground=self.COLORS["accent"],
                    validate="key",
                    validatecommand=(self.root.register(self._valid_entry), "%P"),
                )
                entry.grid(
                    row=row,
                    column=col,
                    padx=(1 if col % BOX_SIZE else 3, 1),
                    pady=(1 if row % BOX_SIZE else 3, 1),
                    ipadx=4,
                    ipady=6,
                )
                entry.bind("<KeyRelease>", lambda event, r=row, c=col: self._on_edit(r, c))
                entry_row.append(entry)
            self.entries.append(entry_row)

        controls = tk.Frame(outer, bg=self.COLORS["window"])
        controls.pack(fill="x", pady=(16, 0))
        ttk.Label(controls, text="Difficulty").pack(side="left")
        difficulty_box = ttk.Combobox(
            controls,
            textvariable=self.difficulty,
            values=("Easy", "Medium", "Hard"),
            state="readonly",
            width=9,
        )
        difficulty_box.pack(side="left", padx=(7, 14))

        self._button(controls, "New puzzle", self.new_game).pack(side="left", padx=(0, 6))
        self._button(controls, "Check", self.check_board).pack(side="left", padx=(0, 6))
        self._button(controls, "Solve", self.solve_game).pack(side="left")

        self.status = tk.StringVar(value="Fill each row, column, and 3 x 3 box with 1-9.")
        tk.Label(
            outer,
            textvariable=self.status,
            font=("Segoe UI", 10),
            bg=self.COLORS["window"],
            fg=self.COLORS["text"],
            anchor="w",
        ).pack(fill="x", pady=(12, 0))

    def _button(self, parent: tk.Widget, label: str, command: object) -> ttk.Button:
        return ttk.Button(parent, text=label, command=command)

    @staticmethod
    def _valid_entry(proposed: str) -> bool:
        return proposed == "" or (len(proposed) == 1 and proposed in "123456789")

    def _on_edit(self, row: int, col: int) -> None:
        entry = self.entries[row][col]
        if entry.cget("state") != "disabled":
            entry.configure(bg=self.COLORS["board"])
        self.status.set("Fill each row, column, and 3 x 3 box with 1-9.")

    def new_game(self) -> None:
        clue_counts = {"Easy": 40, "Medium": 34, "Hard": 29}
        self.puzzle, self.solution = make_puzzle(clue_counts[self.difficulty.get()])
        for row in range(SIZE):
            for col in range(SIZE):
                entry = self.entries[row][col]
                entry.configure(state="normal", bg=self.COLORS["board"], fg=self.COLORS["text"])
                entry.delete(0, tk.END)
                value = self.puzzle[row][col]
                if value:
                    entry.insert(0, str(value))
                    entry.configure(
                        state="disabled",
                        disabledbackground=self.COLORS["given"],
                        disabledforeground=self.COLORS["text"],
                    )
        self.status.set(f"{self.difficulty.get()} puzzle ready. Each puzzle has one solution.")

    def check_board(self) -> None:
        empty_count = 0
        wrong_count = 0
        for row in range(SIZE):
            for col in range(SIZE):
                entry = self.entries[row][col]
                if self.puzzle[row][col]:
                    continue
                value = entry.get()
                if not value:
                    empty_count += 1
                    entry.configure(bg=self.COLORS["board"])
                elif int(value) != self.solution[row][col]:
                    wrong_count += 1
                    entry.configure(bg=self.COLORS["wrong"])
                else:
                    entry.configure(bg=self.COLORS["correct"])

        if wrong_count:
            self.status.set(f"{wrong_count} incorrect cell{'s' if wrong_count != 1 else ''}. Keep going.")
        elif empty_count:
            self.status.set(f"So far, so good. {empty_count} cell{'s' if empty_count != 1 else ''} left.")
        else:
            self.status.set("Solved. Nicely done!")

    def solve_game(self) -> None:
        board = [row[:] for row in self.puzzle]
        solve_board(board)
        for row in range(SIZE):
            for col in range(SIZE):
                entry = self.entries[row][col]
                if not self.puzzle[row][col]:
                    entry.configure(state="normal", bg=self.COLORS["correct"])
                    entry.delete(0, tk.END)
                    entry.insert(0, str(board[row][col]))
                    entry.configure(state="disabled", disabledbackground=self.COLORS["correct"])
        self.status.set("Solved with backtracking. Start a new puzzle to play again.")


def main() -> None:
    root = tk.Tk()
    SudokuApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
