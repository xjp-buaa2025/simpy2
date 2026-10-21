"""Self-contained relay. Imports no scheduling/backend modules."""
import vr_mirror_protocol
from tools.vr_mirror_host import main

if __name__ == '__main__':
    main(vr_mirror_protocol)
