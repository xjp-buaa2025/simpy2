"""Development launcher for the independent image relay."""
from app.api import vr_mirror
from tools.vr_mirror_host import main

if __name__ == '__main__':
    main(vr_mirror)
