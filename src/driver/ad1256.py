from src.settings import Settings

from .spi_driver import SPIDriver
from .enums import ScanMode



# gain channel
ADS1256_GAIN_E = {'ADS1256_GAIN_1' : 0, # GAIN   1
                  'ADS1256_GAIN_2' : 1,	# GAIN   2
                  'ADS1256_GAIN_4' : 2,	# GAIN   4
                  'ADS1256_GAIN_8' : 3,	# GAIN   8
                  'ADS1256_GAIN_16' : 4,# GAIN  16
                  'ADS1256_GAIN_32' : 5,# GAIN  32
                  'ADS1256_GAIN_64' : 6,# GAIN  64
                 }

# data rate
ADS1256_DRATE_E = {'ADS1256_30000SPS' : 0xF0, # reset the default values
                   'ADS1256_15000SPS' : 0xE0,
                   'ADS1256_7500SPS' : 0xD0,
                   'ADS1256_3750SPS' : 0xC0,
                   'ADS1256_2000SPS' : 0xB0,
                   'ADS1256_1000SPS' : 0xA1,
                   'ADS1256_500SPS' : 0x92,
                   'ADS1256_100SPS' : 0x82,
                   'ADS1256_60SPS' : 0x72,
                   'ADS1256_50SPS' : 0x63,
                   'ADS1256_30SPS' : 0x53,
                   'ADS1256_25SPS' : 0x43,
                   'ADS1256_15SPS' : 0x33,
                   'ADS1256_10SPS' : 0x20,
                   'ADS1256_5SPS' : 0x13,
                   'ADS1256_2d5SPS' : 0x03
                  }

# registration definition
REG_E = {'REG_STATUS' : 0,  # x1H
         'REG_MUX' : 1,     # 01H
         'REG_ADCON' : 2,   # 20H
         'REG_DRATE' : 3,   # F0H
         'REG_IO' : 4,      # E0H
         'REG_OFC0' : 5,    # xxH
         'REG_OFC1' : 6,    # xxH
         'REG_OFC2' : 7,    # xxH
         'REG_FSC0' : 8,    # xxH
         'REG_FSC1' : 9,    # xxH
         'REG_FSC2' : 10,   # xxH
        }

# command definition
CMD = {'CMD_WAKEUP' : 0x00,     # Completes SYNC and Exits Standby Mode 0000  0000 (00h)
       'CMD_RDATA' : 0x01,      # Read Data 0000  0001 (01h)
       'CMD_RDATAC' : 0x03,     # Read Data Continuously 0000   0011 (03h)
       'CMD_SDATAC' : 0x0F,     # Stop Read Data Continuously 0000   1111 (0Fh)
       'CMD_RREG' : 0x10,       # Read from REG rrr 0001 rrrr (1xh)
       'CMD_WREG' : 0x50,       # Write to REG rrr 0101 rrrr (5xh)
       'CMD_SELFCAL' : 0xF0,    # Offset and Gain Self-Calibration 1111    0000 (F0h)
       'CMD_SELFOCAL' : 0xF1,   # Offset Self-Calibration 1111    0001 (F1h)
       'CMD_SELFGCAL' : 0xF2,   # Gain Self-Calibration 1111    0010 (F2h)
       'CMD_SYSOCAL' : 0xF3,    # System Offset Calibration 1111   0011 (F3h)
       'CMD_SYSGCAL' : 0xF4,    # System Gain Calibration 1111    0100 (F4h)
       'CMD_SYNC' : 0xFC,       # Synchronize the A/D Conversion 1111   1100 (FCh)
       'CMD_STANDBY' : 0xFD,    # Begin Standby Mode 1111   1101 (FDh)
       'CMD_RESET' : 0xFE,      # Reset to Power-Up Values 1111   1110 (FEh)
      }


class ADS1256:
    def __init__(self, settings: Settings):
        self.rst_pin = settings.spi.rst_pin
        self.cs_pin = settings.spi.cs_pin
        self.drdy_pin = settings.spi.drdy_pin

        self.scan_mode = ScanMode.SingleMode
        self.spi = SPIDriver(settings)

        self.__init_adc()
    
    def __init_adc(self):
        if self.spi.module_init() != 0:
            return -1
        self.reset()
        chip_id = self.read_chip_id()
        if chip_id == 3 :
            print("ID Read success  ")
        else:
            print("ID Read failed   ")
            return -1
        self.config_adc(ADS1256_GAIN_E['ADS1256_GAIN_1'], ADS1256_DRATE_E['ADS1256_30000SPS'])
        return 0

    # Hardware reset
    def reset(self):
        self.spi.digital_write(self.rst_pin, 1)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.rst_pin, 0)
        self.spi.delay_ms(200)
        self.spi.digital_write(self.rst_pin, 1)

    def write_cmd(self, reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([reg])
        self.spi.digital_write(self.cs_pin, 1)#cs 1

    def write_reg(self, reg, data):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([CMD['CMD_WREG'] | reg, 0x00, data])
        self.spi.digital_write(self.cs_pin, 1)#cs 1

    def read_data(self, reg):
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([CMD['CMD_RREG'] | reg, 0x00])
        data = self.spi.spi_readbytes(1)
        self.spi.digital_write(self.cs_pin, 1)#cs 1

        return data

    def wait_drdy(self):
        for i in range(0,400000,1):
            if self.spi.digital_read(self.drdy_pin) == 0:

                break
        if i >= 400000:
            print ("Time Out ...\r\n")

    def read_chip_id(self):
        self.wait_drdy()
        id = self.read_data(REG_E['REG_STATUS'])
        id = id[0] >> 4
        # print 'ID',id
        return id

    #The configuration parameters of ADC, gain and data rate
    def config_adc(self, gain, drate):
        self.wait_drdy()
        buf = [0,0,0,0,0,0,0,0]
        buf[0] = (0<<3) | (1<<2) | (0<<1)
        buf[1] = 0x08
        buf[2] = (0<<5) | (0<<3) | (gain<<0)
        buf[3] = drate

        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([CMD['CMD_WREG'] | 0, 0x03])
        self.spi.spi_writebyte(buf)

        self.spi.digital_write(self.cs_pin, 1)#cs 1
        self.spi.delay_ms(1)

    def set_channel(self, channel):
        if channel > 7:
            return 0
        self.write_reg(REG_E['REG_MUX'], (channel<<4) | (1<<3))

    def set_differential_channel(self, channel):
        if channel == 0:
            self.write_reg(REG_E['REG_MUX'], (0 << 4) | 1) 	#Diffchannel  AIN0-AIN1
        elif channel == 1:
            self.write_reg(REG_E['REG_MUX'], (2 << 4) | 3) 	#Diffchannel   AIN2-AIN3
        elif channel == 2:
            self.write_reg(REG_E['REG_MUX'], (4 << 4) | 5) 	#Diffchannel    AIN4-AIN5
        elif channel == 3:
            self.write_reg(REG_E['REG_MUX'], (6 << 4) | 7) 	#Diffchannel   AIN6-AIN7

    def set_mode(self, mode: ScanMode):
        self.scan_mode = mode

    def read_ADC_data(self):
        self.wait_drdy()
        self.spi.digital_write(self.cs_pin, 0)#cs  0
        self.spi.spi_writebyte([CMD['CMD_RDATA']])
        # config.delay_ms(10)

        buf = self.spi.spi_readbytes(3)
        self.spi.digital_write(self.cs_pin, 1)#cs 1
        read = (buf[0]<<16) & 0xff0000
        read |= (buf[1]<<8) & 0xff00
        read |= (buf[2]) & 0xff
        if read & 0x800000:
            read &= 0xF000000
        return read

    def get_channel_value(self, channel):
        if self.scan_mode == ScanMode.SingleMode:
            if channel >= 8:
                return 0
            self.set_channel(channel)
            self.write_cmd(CMD['CMD_SYNC'])
            # config.delay_ms(10)
            self.write_cmd(CMD['CMD_WAKEUP'])
            # config.delay_ms(200)
            value = self.read_ADC_data()
        else:
            if channel>=4:
                return 0
            self.set_differential_channel(channel)
            self.write_cmd(CMD['CMD_SYNC'])
            # config.delay_ms(10) 
            self.write_cmd(CMD['CMD_WAKEUP'])
            # config.delay_ms(10) 
            value = self.read_ADC_data()
        return value * 5.0 / 0x7fffff

    def get_all(self):
        for i in range(0,8,1):
            yield self.get_channel_value(i)

    def get_specific_channels(self, channels: list[int]):
        for i in channels:
            yield self.get_channel_value(i)
