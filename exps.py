class ApiBase:
    def helper(self):
        print("Helper")


class Api(ApiBase):
    def method(self):
        print("method")


if __name__ == "__main__":
    print(dir(ApiBase))
    print(dir(Api))
