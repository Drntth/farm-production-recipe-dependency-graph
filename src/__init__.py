from pathlib import Path

from src.loaders.json_loader import load_data


def main():
    dataset = load_data(Path("data"))
    print(dataset.summary())


if __name__ == "__main__":
    main()
