import string
import random

import argh


def _generate_secure_random():
    charset = string.digits + string.letters
    random_generator = random.SystemRandom()

    return "".join([random_generator.choice(charset) for _ in range(50)])


PYRAMID_INI_TEMPLATE = """\
[main]

cubicweb.session.secret = SECRET_1
cubicweb.auth.authtkt.session.secret = SECRET_2
cubicweb.auth.authtkt.persistent.secret = SECRET_3
cubicweb.auth.authtkt.session.secure = no
cubicweb.auth.authtkt.persistent.secure = no"""


def generate_pyramid_ini():
    # TODO
    # -i --instance
    # -f --force
    print(PYRAMID_INI_TEMPLATE.replace("SECRET_1", _generate_secure_random())
                              .replace("SECRET_2", _generate_secure_random())
                              .replace("SECRET_3", _generate_secure_random()))


parser = argh.ArghParser()
parser.add_commands([generate_pyramid_ini])

if __name__ == '__main__':
    parser.dispatch()
