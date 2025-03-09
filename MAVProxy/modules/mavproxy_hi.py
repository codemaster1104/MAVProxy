from MAVProxy.modules.lib import mp_module

class HiModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(HiModule, self).__init__(mpstate, "hi", "prints HII")
        self.add_command('hi', self.cmd_hi, 'Print HII')
        
    def cmd_hi(self, args):
        '''handle hi command'''
        print("HII")

def init(mpstate):
    '''initialize module'''
    return HiModule(mpstate)