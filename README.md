# PyQT QO-100 Hamlib Helper

A PyQT helper for using QO-100 satellites with two radios/SDR controlled over the network with Hamlib. 

* Synchronises transmit and receive frequencies one off or links them.
* Controls PTT via CAT
* Can mutes local SDR audio on transmit  

I've removed the rx offset function for now as it's was causing bother.

This will likely work for noone but me but me and there's no error checking but to configure it's expecting hamlib RX to be 10498 and TX 432MHz.  Set txrxOffset to the difference between TX/RX frequency, the hosts and ports of the hamlib network listeners and the pulseDev to be the audio sink number you wish to mute. You can find the device with:

import pulsectl
pulse = pulsectl.Pulse('my-client-name')
pulse.sink_list()

I'll try and get back to making it a bit cleaner

## Installation Requirements

* pulsectl
* pyqt5
* python-pyqt5
