import pandas as pd

def generate_summary(file_path: str):

    df = pd.read_csv(file_path)

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns)
    }