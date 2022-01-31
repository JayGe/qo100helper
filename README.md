# PyQT QO-100 Hamlib Helper

A PyQT helper for using QO-100 satellites with two radios/SDR controlled over the network with Hamlib. 

![application screen shot](https://raw.githubusercontent.com/JayGe/qo100helper/master/screenshot.png)

* Synchronises transmit and receive frequencies one off or links them.
* Controls PTT via CAT
* Can mute local SDR audio device on transmit  

The TX offset requires either a manual sync each time it's changed or will be constantly altered when LINK is selected. Offset can't be changed while PTT is on. 

This will likely work for noone but me but me and there's no error checking but to configure it's expecting hamlib RX to be 10498 and TX 432MHz.  

Set txrxOffsetFixed to the difference between TX/RX frequency, the hosts and ports of the hamlib network listeners and the soundcardName to match your soundcard to be muted. You can get the list with the following in Python:

import pulsectl
pulse = pulsectl.Pulse('my-client-name')
for x in pulse.sink_list() :
  print x

## Installation Requirements

* pulsectl
* pyqt5
* python-pyqt5
