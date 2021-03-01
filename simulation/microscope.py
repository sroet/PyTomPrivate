import os
import numpy as xp
import pytom.simulation.physics as physics
from scipy.optimize import curve_fit


def fourier_array(shape, nyquist):
    """
    @param shape: tuple with the size on each dimension
    @param shape: tuple of ints
    @param spacing: pixel or voxel spacing
    @type spacing: float
    @return: fourier space frequencies
    @rtype: numpy.ndarray
    """
    assert type(shape) == tuple, "shape needs to be a tuple of dimenion sizes, dimenions need to be equal"
    assert len(set(shape)) == 1, "dimensions are not identical"
    assert len(shape) <= 3, "too many dimensions, 3 is max"

    size = shape[0]

    d = xp.arange(-nyquist, nyquist, 2. * nyquist / size)

    if len(shape) == 2:
        grids = xp.meshgrid(d,d)
    else:
        grids = xp.meshgrid(d, d, d)

    # Wave vector and direction
    k = xp.sqrt(sum([d**2 for d in grids]))  # xz ** 2 + yz ** 2 + zz ** 2)
    # k2 = k ** 2
    # k4 = k2 ** 2
    return k  # , k2, k4


def sinc_square(x, p1, p2, p3, p4):
    return p1 * (xp.sin(xp.pi*(x-p2)*p3) / (xp.pi*(x-p2)*p3))**2 + p4


def fit_sinc_square(xdata,ydata):
    # Here you give the initial parameters for p0 which Python then iterates over
    # to find the best fit
    popt, pcov = curve_fit(sinc_square,xdata,ydata,p0=(1.0, 1.0, 1.0, 1.0)) #THESE PARAMETERS ARE USER DEFINED

    # print(popt) # This contains your two best fit parameters

    # Performing sum of squares
    p1 = popt[0]
    p2 = popt[1]
    p3 = popt[2]
    p4 = popt[3]
    residuals = ydata - sinc_square(xdata,p1,p2,p3,p4)
    fres = sum(residuals**2)

    print(f'chi-square value for fitting sinc function is {fres}') #THIS IS YOUR CHI-SQUARE VALUE!

    # Visually inspect fit of function.
    #
    # import matplotlib
    # matplotlib.use('Qt5Agg')
    # import matplotlib.pyplot as plt
    #
    # xaxis = xp.linspace(0,1,100) # we can plot with xdata, but fit will not look good
    # curve_y = sinc_square(xaxis,p1,p2,p3,p4)
    # plt.plot(xdata,ydata,'*')
    # plt.plot(xaxis,curve_y,'-')
    # plt.show()

    # Return the sin parameters
    return p1,p2,p3,p4


def radial_average(image):
    """
    This calculates the radial average of an image. When used for ctf, dqe, and mtf type display, input should be in
    Fourier space.
    """
    assert len(image.shape) == 2, "radial average calculation only works for 2d image arrays"
    assert len(set(image.shape)) == 1, 'differently size dimension, cannot perform radial averaging'

    size = image.shape[0]
    center = (size - 1) / 2
    x, y = xp.meshgrid(xp.arange(size), xp.arange(size))
    R = xp.sqrt((x - center) ** 2 + (y - center) ** 2)

    f = lambda r: image[(R >= r - .5) & (R < r + .5)].mean()
    r = xp.linspace(1, size // 2, num=size // 2)
    mean = xp.vectorize(f)(r)

    return r, mean


def display_microscope_function(image, form='', complex=False):
    import matplotlib
    matplotlib.use('Qt5Agg')
    import matplotlib.pyplot as plt

    if complex:
        r1, m1 = radial_average(image.real)
        r2, m2 = radial_average(image.imag)
    else:
        r1, m1 = radial_average(image)

    fig, ax = plt.subplots()
    ax.plot(r1, m1, label=form)
    if complex: ax.plot(r2, m2, label='imaginary')
    ax.legend()
    # plt.savefig(f'{form}.png')
    # plt.imshow()
    plt.show()
    return


def read_detector_csv(filename):
    data = xp.genfromtxt(filename,delimiter=',',dtype=xp.float32)
    x = data[:,0]
    y = data[:,1]
    return x,y


def create_detector_response(detector, response_function, image_size, voltage=300E3, binning=1, folder='', display=False):
    """
    CSV file containing the detector curve should on the x-axis be expressed as fraction of Nyquist (between 0 and 1)
    and on the y-axis as the MTF or DQE value (also between 0 and 1).

    @param detector: eg. 'K2SUMMIT', 'FALCONII'
    @type detector: string
    @param response_function: eg. 'DQE' or 'MTF'
    @type response_function: string
    @param voltage: Voltage of detector operation (in V not kV)
    @type voltage: float
    @param image: image size
    @type image: int
    @param folder: Folder where csv file with detector functions are stored. If not provided assume they are present
    in the current directory. eg. '/data2/mchaillet/simulation/detectors'
    @type folder: string

    @return: the detector response function
    @rtype 2d array (numpy)

    @author: Marten Chaillet
    """
    name = f'{detector}_{response_function}_{int(voltage*1E-3)}kV'
    if folder == '':
        filename = f'{name}.csv'
    else:
        filename = os.path.join(folder, f'{name}.csv')
    print(f'Determining {response_function} for {detector}')
    # data is a function of spatial frequency
    qdata,ydata = read_detector_csv(filename)
    params = fit_sinc_square(qdata,ydata)

    sampling_image_size = image_size * binning
    # fraction of nyquist maximum
    # Ny = 1
    # R, Y = xp.meshgrid(xp.arange(-Ny, Ny, 2. * Ny / (shape[0])), xp.arange(-Ny, Ny, 2. * Ny / (shape[1])))
    # r = xp.sqrt(R ** 2 + Y ** 2)
    r = fourier_array((sampling_image_size,)*2, 1)  # nyquist is 1, as the fraction of nyquist maximum

    detector_response = sinc_square(r, params[0], params[1], params[2], params[3])

    if binning > 1:
        # crop the detector function
        cut = sampling_image_size // 2 - image_size // 2
        detector_response = detector_response[cut:-cut, cut:-cut]

    if display:
        display_microscope_function(detector_response, form=response_function, complex=False)

    return detector_response


def transmission_function(sliced_potential, voltage, dz):
    # wavelength
    Lambda = physics.wavelength_eV2m(voltage)
    # relative mass
    relative_mass = physics.constants["me"] + physics.constants["el"] * voltage / (physics.constants["c"] ** 2)
    # sigma_transfer
    sigma_transfer = 2 * xp.pi * relative_mass * physics.constants["el"] * Lambda / (physics.constants["h"] ** 2)

    return xp.exp(1j * sigma_transfer * sliced_potential * dz)


def fresnel_propagator(image_size, pixel_size, voltage, dz):
    Lambda = physics.wavelength_eV2m(voltage)

    #todo Up for removal, but test simulator first
    # xwm = pixel_size * (image_size)  # pixelsize for multislice * size sample
    # q_true_pix_m = 1 / xwm  # spacing in Fourier space
    # x_line = xp.arange(-(image_size - 1) / 2, (image_size - 1) / 2 + 1, 1)
    # [xv, yv] = xp.meshgrid(x_line, x_line)
    # q_m = xp.sqrt(xv ** 2 + yv ** 2) * q_true_pix_m  # frequencies in Fourier domain

    nyquist = 1 / (2 * pixel_size)
    k = fourier_array((image_size,)*2, nyquist)

    return xp.exp(-1j * xp.pi * Lambda * (k ** 2) * dz)


def create_ctf(shape, spacing, defocus, amplitude_contrast, voltage, Cs, sigma_decay=0.4,
               display=False):
    """
    This function models a non-complex CTF. It can be used for both a 2d or 3d function. It describes a ctf after
    detection (and is therefore not complex).

    @param Dz: defocus value in m
    @type Dz: C{float}
    @param A: Amplitude contrast fraction (e.g., 0.1)
    @type A: C{float}
    @param Voltage: acceleration voltage in eV
    @type Voltage: C{float}
    @param Cs: sphertical abberation in m
    @type Cs: C{float}
    @param k4: frequencies in fourier space to power 4
    @type k4: L{numpy.ndarray}
    @param k2: frequencies in fourier space squared
    @type k2: L{numpy.ndarray}
    @return: CTF in Fourier space
    @rtype: L{numpy.ndarray}
    """
    nyquist = 1 / (2 * spacing)
    k = fourier_array(shape, nyquist)
    lmbd = physics.wavelength_eV2m(voltage)

    chi = xp.pi * lmbd * defocus * k**2 - 0.5 * xp.pi * Cs * lmbd ** 3 * k ** 4

    ctf = - xp.sqrt(1. - amplitude_contrast ** 2) * xp.sin(chi) - amplitude_contrast * xp.cos(chi)

    decay = 1 if sigma_decay <= 0 else xp.exp(-(k / (sigma_decay * nyquist)) ** 2)
    ctf *= decay

    if display:
        if len(shape)==2:
            display_microscope_function(ctf, form='ctf', complex=False)
        else:
            display_microscope_function(ctf[:,:,shape[2]//2], form='ctf', complex=False)

    return ctf


def create_simple_complex_ctf(image_shape, pixel_size, Dz, voltage=300E3, Cs=2.7E-3, sigma_decay=0.4, display=False):
    """
    Adapated from Vulovic et al., 2013. Returns a complex contrast transfer function. Dimensions of input image or
    volume should be equal. Only phase part of CTF.

    @param vol:
    @type vol:
    @param pix_size:
    @type pix_size:
    @param Dz:
    @type Dz:
    @param voltage:
    @type voltage:
    @param Cs:
    @type Cs:
    @param sigma_decay_ctf:
    @type sigma_decay_ctf:
    @param amplitude_contrast:
    @type amplitude_contrast:

    @return:
    @rtype:

    @author: Marten Chaillet
    """
    assert len(image_shape) == 2, print('image shape should be a tuple of length 2')
    assert len(set(image_shape)) == 1, print('invalid input image/volume for create CTF, dimensions need to be equal.')

    lmbd = physics.wavelength_eV2m(voltage)

    nyquist = 1 / (2 * pixel_size)

    k = fourier_array(image_shape, nyquist)

    complex_ctf = xp.exp( -1j * xp.pi / 2 * (Cs * (lmbd ** 3) * (k ** 4) - 2 * Dz * lmbd * (k ** 2)) )

    # Decay function
    decay = 1 if sigma_decay <= 0 else xp.exp(-(k / (sigma_decay * nyquist)) ** 2)
    complex_ctf *= decay

    # visual inspection of CTF
    if display:
        display_microscope_function(complex_ctf, form='ctf', complex=True)

    return complex_ctf


def create_complex_ctf(image_shape, pixel_size, defocus, voltage=300E3, Cs=2.7E-3, Cc=2.7E-3,
                           energy_spread=0.7, illumination_aperture=0.030E-3, objective_diameter=100E-6,
                           focus_length=4.7E-3, astigmatism=0.0, astigmatism_angle=0.0, display=False):
    """
        # parameters for extended CTF function (InSilicoTEM)
    chromatic_abberation    = 2.7E-3 # C_c
    energy_spread           = 0.7 # deltaE
    illumination_aperture   = 0.030E-3 # a_i
    objective_diameter      = 100E-6 #
    focus_length            = 4.7E-3 # focal distance
    astigmatism in 0.0E-9
    astigmatism angle in degrees

    Adapated from Vulovic et al., 2013. Returns a complex contrast transfer function. Dimensions of input image or
    volume should be equal. Only phase part of CTF.

    @param vol:
    @type vol:
    @param pix_size:
    @type pix_size:
    @param Dz:
    @type Dz:
    @param voltage:
    @type voltage:
    @param Cs:
    @type Cs:
    @param sigma_decay_ctf:
    @type sigma_decay_ctf:
    @param amplitude_contrast:
    @type amplitude_contrast:

    @return:
    @rtype:

    @author: Marten Chaillet
    """
    from scipy.ndimage import gaussian_filter

    assert len(image_shape) == 2, print('image shape should be a tuple of length 2')
    assert len(set(image_shape)) == 1, print('invalid input image/volume for create CTF, dimensions need to be equal.')

    image_size = image_shape[0]

    lmbd = physics.wavelength_eV2m(voltage)

    q_true = 1 / (image_size * pixel_size)

    dfsh = defocus + astigmatism
    dfln = defocus - astigmatism
    inratioqqs = xp.sqrt(dfsh/defocus)
    inratioqlq = xp.sqrt(defocus/dfln)

    x = xp.arange(-(image_size//2), abs(-image_size//2), 1)
    xx, yy = xp.meshgrid(x, x)
    xdot = xx * xp.cos(astigmatism_angle*xp.pi/180) - yy * xp.sin(astigmatism_angle*xp.pi/180)
    ydot = xx * xp.sin(astigmatism_angle*xp.pi/180) - yy * xp.cos(astigmatism_angle*xp.pi/180)
    q = xp.sqrt((xdot / inratioqlq) ** 2 + (ydot * inratioqqs) ** 2) * q_true
    qsym = xp.sqrt(xdot ** 2 + ydot ** 2) * q_true

    # print(r)
    chi = 0.5 * xp.pi * (Cs * (lmbd ** 3) * (qsym ** 4) - 2 * defocus * lmbd * (q ** 2))
    complex_ctf = xp.cos(chi) - 1j * xp.sin(chi)

    # chromatic envelope
    h = Cc * energy_spread / voltage
    nominator = xp.pi * lmbd * q ** 2 * h
    denominator = 4 * xp.sqrt(xp.log(2))
    chromatic_envelope = xp.exp(- (nominator / denominator) ** 2)
    # spatial envelope
    nums = (xp.pi * Cs * lmbd ** 2 * q ** 3 - xp.pi * defocus * q) ** 2 * illumination_aperture ** 2
    spatial_envelope = xp.exp(- nums / xp.log(2))
    # full envelope
    envelope = chromatic_envelope * spatial_envelope

    # aperture function
    aperture = xp.ones(image_shape)
    qmax = 2 * xp.pi * objective_diameter / (lmbd * focus_length)
    aperture[q > qmax] = 0
    gaussian_filter(aperture, sigma=3, output=aperture)

    complex_ctf *= (envelope * aperture)

    # print(complex_CTF.shape, K.shape, A.shape)
    # visual inspection of CTF
    if display:
        display_microscope_function(complex_ctf, form='ctf', complex=True)

    return complex_ctf