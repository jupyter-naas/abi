# Transform SPARQL results to list of dictionaries using the labels as keys
def results_to_list(results: list[dict]) -> list[dict]:
    data = []
    for row in results:
        data_dict = {}
        for key in row.labels:
            data_dict[key] = str(row[key]) if row[key] else None
        data.append(data_dict)
    return data