class OptimusPrime:
    """
    Central controller for the Optimus Prime trading system.
    """

    def __init__(self):
        self.name = "Optimus Prime"
        self.status = "INITIALIZING"

    def start(self):
        self.status = "ONLINE"
        print(f"{self.name} is {self.status}.")

    def shutdown(self):
        self.status = "OFFLINE"
        print(f"{self.name} is {self.status}.")