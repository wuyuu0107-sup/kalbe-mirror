def flatten_json(data, parent="", sep="."):

    """
    Flatten a nested dictionary using dot notation.
    Example: {"a": {"b": 1}} -> {"a.b": 1}
    """
    
    result = {}
    for key, value in data.items():

        if parent:
            new_key = parent + sep + key
        else:
            new_key = key

        if isinstance(value, dict):
            inner_flat = flatten_json(value, new_key, sep)
            for k, v in inner_flat.items():
                result[k] = v
        else:
            result[new_key] = value
    return result


def json_to_csv(data, writer):
    flat = flatten_json(data)

    columns = list(flat.keys())
    writer.writerow(columns)

    row = [flat[col] for col in columns]
    writer.writerow(row)
