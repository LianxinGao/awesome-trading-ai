import json
import os


class ObjectStore:
    def __init__(self, path: str):
        self.data_path = path

    def save(self, key: str, value: str | list | dict, namespace=None):
        path = self.data_path

        if isinstance(value, list) or isinstance(value, dict):
            value = json.dumps(value, indent=2, ensure_ascii=False)
        if namespace is not None:
            path = os.path.join(path, namespace)
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, key + ".json")

        with open(file_path, "w") as f:
            f.write(value)

    def load(self, key: str, namespace=None):
        path = self.data_path
        if namespace is not None:
            path = os.path.join(path, namespace)
        file_path = os.path.join(path, key + ".json")
        if not os.path.exists(file_path):
            return None
        print("opening file", file_path)
        with open(file_path, "r") as f:
            return f.read()

    def load_all(self, namespace=None):
        path = self.data_path
        if namespace is not None:
            path = os.path.join(path, namespace)
        data = []
        if not os.path.exists(path):
            return data
        for file in os.listdir(path):
            obj = self.load_obj(file.replace(".json", ""), None, namespace)
            data.append(obj)
        return data

    def load_obj(self, key: str, Cls=None, namespace=None):
        data = self.load(key, namespace)
        if data is None:
            return None
        if Cls is None:
            return json.loads(data)

        return Cls.model_validate_json(data)