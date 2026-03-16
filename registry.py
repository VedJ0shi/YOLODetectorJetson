
class SurveillanceRegister:
    '''
    In-memory store for tracked objects
    '''

    def __init__(self):
        self.watch = {}
        self.catch = {}
        


#Singleton instance
Object_register = SurveillanceRegister()