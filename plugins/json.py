import json
import os


class JsonFormat:
    @staticmethod
    def get_format_name():
        return "json"

    @staticmethod
    def to_json(params):
        input_filename = params.get('input')

        if not input_filename or not os.path.exists(input_filename):
            return None

        with open(input_filename, "r") as f:
            return f.read()

    @staticmethod
    def to_chart(params):
        output_filename = params.get('output', "")

        with open(output_filename, "w") as f:
            f.write(params.get('input', ""))


def get_class():
    return JsonFormat
