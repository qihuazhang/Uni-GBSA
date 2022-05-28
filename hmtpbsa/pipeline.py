import os
import shutil
import argparse
import configparser
from tabnanny import verbose
import pandas as pd

from hmtpbsa.pbsa.pbsarun import PBSA
from hmtpbsa.utils import generate_index_file
from hmtpbsa.simulation.mdrun import GMXEngine
from hmtpbsa.simulation.topology import build_topol, build_protein
from hmtpbsa.settings import logging, DEFAULT_CONFIGURE_FILE, GMXEXE

def traj_pipeline(complexfile, trajfile, topolfile, indexfile, pbsaParas=None, mmpbsafile=None, verbose=False):
    """
    A pipeline for calculate GBSA/PBSA for trajectory
    
    Args:
      complexfile: The name of the PDB file containing the protein-ligand complex.
      trajfile: the trajectory file, in pdb format
      topolfile: The topology file of the complex.
      indexfile: the index file for the complex
      mode: gb or tm. Defaults to gb
      dec: whether to decompose the free energy into its components. Defaults to False
      debug: if True, will print out all the debug messages. Defaults to False
    
    Returns:
      detal_G is a dictionary, the key is the mode, the value is a list, the first element is the
    average value, the second element is the standard deviation.
    """

    reresfile = complexfile[:-4]+'_reres.pdb'
    cmd = '%s editconf -f %s -o %s -resnr 1 >/dev/null 2>&1'%(GMXEXE, complexfile, reresfile)
    RC = os.system(cmd)
    if RC!=0:
       raise Exception('Error conver %s to %s'%(complexfile, reresfile))
    pbsa = PBSA()
    mmpbsafile = pbsa.set_paras(complexfile=reresfile, trajectoryfile=trajfile, topolfile=topolfile, indexfile=indexfile, pbsaParas=pbsaParas, mmpbsafile=mmpbsafile)
    pbsa.run(verbose=verbose)
    detal_G = pbsa.extract_result()
    print("mode    detal_G(kcal/mole)    Std. Dev.")
    for k, v in detal_G.items():
        print('%4s    %18.4f    %9.4f'%(k, v[0], v[1]))
    return detal_G

def base_pipeline(receptorfile, ligandfiles, paras, mmpbsafile=None, outfile='BindingEnergy.csv', verbose=False):
    """
    This function takes a receptorfile and ligandfile, and build a complex.pdb and complex.top file
    
    Args:
      receptorfile: the file name of the receptor pdb file
      ligandfile: the name of the ligand file
      paras: a dictionary of parameters for the pipeline.
    """
    simParas = paras['simulation']
    pbsaParas = paras['PBSA']

    receptorfile = os.path.abspath(receptorfile)
    logging.info('Build protein topology.')
    receptor = build_protein(receptorfile, forcefield=simParas['proteinforcefield'])

    detalGdict = {'name':[]}
    for k in ['GB','PB', 'gb', 'pb']:
        if k in pbsaParas['modes']:
            detalGdict[k.upper()] = []
            detalGdict['%s_err'%k.upper()] = []
    
    cwd = os.getcwd()
    for ligandfile in ligandfiles:
        ligandfile = os.path.abspath(ligandfile)
        ligandName = os.path.split(ligandfile)[-1][:-4]
        if not os.path.exists(ligandName):
            os.mkdir(ligandName)
        os.chdir(ligandName)

        grofile = 'complex.pdb'
        topfile = 'complex.top'
        logging.info('Build ligand topology: %s'%ligandName)
        build_topol(receptor, ligandfile, outpdb=grofile, outtop=topfile, ligandforce=simParas['ligandforcefield'])

        indexfile = generate_index_file(grofile)
        pbsaParas = paras['PBSA']
        detalG = traj_pipeline(grofile, trajfile=grofile, topolfile=topfile, indexfile=indexfile, pbsaParas=pbsaParas, mmpbsafile=mmpbsafile, verbose=verbose)
        detalGdict['name'].append(ligandName)
        for k,v in detalG.items():
            detalGdict[k.upper()].append(v[0])
            detalGdict["%s_err"%k.upper()].append(v[1])
        os.chdir(cwd)
    df = pd.DataFrame(detalGdict)
    df.to_csv(outfile, index=False)


def minim_peipline(receptorfile, ligandfiles, paras, mmpbsafile=None, outfile='BindingEnergy.csv', verbose=False):
    """
    It runs the simulation pipeline for each ligand.
    
    Args:
      receptorfile: The name of the receptor file.
      ligandfiles: a list of ligand files
      paras: a dictionary of parameters
      outfile: the output file name. Defaults to BindingEnergy.csv
    """
    simParas = paras['simulation']
    pbsaParas = paras['PBSA']

    receptorfile = os.path.abspath(receptorfile)
    logging.info('Build protein topology.')
    receptor = build_protein(receptorfile, forcefield=simParas['proteinforcefield'])

    detalGdict = {'name':[]}
    for k in ['GB','PB', 'gb', 'pb']:
        if k in pbsaParas['modes']:
            detalGdict[k.upper()] = []
            detalGdict['%s_err'%k.upper()] = []
    
    cwd = os.getcwd()
    for ligandfile in ligandfiles:
        ligandfile = os.path.abspath(ligandfile)
        ligandName = os.path.split(ligandfile)[-1][:-4]
        if not os.path.exists(ligandName):
            os.mkdir(ligandName)
        os.chdir(ligandName)

        grofile = 'complex.pdb'
        topfile = 'complex.top'
        logging.info('Build ligand topology: %s'%ligandName)
        build_topol(receptor, ligandfile, outpdb=grofile, outtop=topfile, ligandforce=simParas['ligandforcefield'])

        logging.info('Running energy minimization: %s'%ligandName)
        engine = GMXEngine()

        #minimgro, outtop = engine.run_to_minim_pbsa(grofile, topfile, boxtype=simParas['boxtype'], boxsize=simParas['boxsize'], conc=simParas['conc'])
        minimgro, outtop = engine.run_to_minim(grofile, topfile, boxtype=simParas['boxtype'], boxsize=simParas['boxsize'], conc=simParas['conc'], maxsol=simParas['maxsol'])
    
        cmd = '%s editconf -f %s -o %s -resnr 1 >/dev/null 2>&1'%(GMXEXE, minimgro, grofile)
        RC = os.system(cmd)
        if RC!=0:
            raise Exception('Error conver %s to %s'%(minimgro, grofile))
        shutil.copy(topfile, outtop)

        indexfile = generate_index_file(grofile)
        detalG = traj_pipeline(grofile, trajfile=grofile, topolfile=topfile, indexfile=indexfile, pbsaParas=pbsaParas, mmpbsafile=mmpbsafile, verbose=verbose)
        detalGdict['name'].append(ligandName)
        for k,v in detalG.items():
            detalGdict[k.upper()].append(v[0])
            detalGdict["%s_err"%k.upper()].append(v[1])
        if not verbose:
            engine.clean(pdbfile=grofile)
        os.chdir(cwd)
    df = pd.DataFrame(detalGdict)
    df.to_csv(outfile, index=False)

def md_pipeline(receptorfile, ligandfiles, paras, mmpbsafile=None, outfile='BindingEnergy.csv', verbose=False):
    """
    The main function of this script
    
    Args:
      receptorfile: the protein file
      ligandfiles: a list of ligand files
      paras: a dictionary of parameters
      outfile: the output file name. Defaults to BindingEnergy.csv
    """
    simParas = paras['simulation']
    pbsaParas = paras['PBSA']

    receptorfile = os.path.abspath(receptorfile)
    logging.info('Build protein topology.')
    receptor = build_protein(receptorfile, forcefield=simParas['proteinforcefield'])
    detalGdict = {'name':[]}
    for k in ['GB','PB', 'gb', 'pb']:
        if k in pbsaParas['modes']:
            detalGdict[k.upper()] = []
            detalGdict['%s_err'%k.upper()] = []

    cwd = os.getcwd()
    for ligandfile in ligandfiles:
        print('='*80)
        ligandfile = os.path.abspath(ligandfile)
        ligandName = os.path.split(ligandfile)[-1][:-4]
        if not os.path.exists(ligandName):
            os.mkdir(ligandName)
        os.chdir(ligandName)

        grofile = 'complex.pdb'
        topfile = 'complex.top'
        xtcfile = 'traj_com.xtc'
        logging.info('Build ligand topology: %s'%ligandName)
        build_topol(receptor, ligandfile, outpdb=grofile, outtop=topfile, ligandforce=simParas['ligandforcefield'])

        logging.info('Running simulation: %s'%ligandName)
        engine = GMXEngine()
    
        mdgro, mdxtc, outtop = engine.run_to_md(grofile, topfile, boxtype=simParas['boxtype'], boxsize=simParas['boxsize'], conc=simParas['conc'], nsteps=simParas['nsteps'], nframe=simParas['nframe'], eqsteps=simParas['eqsteps'])

        cmd = '%s editconf -f %s -o %s -resnr 1 >/dev/null 2>&1'%(GMXEXE, mdgro, grofile)
        RC = os.system(cmd)
        if RC!=0:
            raise Exception('Error conver %s to %s'%(mdgro, grofile))

        shutil.copy(topfile, outtop)
        shutil.copy(mdxtc, xtcfile)

        #logging.info('Running GBSA: %s'%ligandName)
        indexfile = generate_index_file(grofile)
        if 'startframe' not in pbsaParas:
            pbsaParas["startframe"] = 2
        detalG = traj_pipeline(grofile, trajfile=xtcfile, topolfile=topfile, indexfile=indexfile, pbsaParas=pbsaParas, mmpbsafile=mmpbsafile, verbose=verbose)
        detalGdict['name'].append(ligandName)
        for k,v in detalG.items():
            detalGdict[k.upper()].append(v[0])
            detalGdict["%s_err"%k.upper()].append(v[1])
        if not verbose:
            engine.clean(pdbfile=grofile)
        os.chdir(cwd)
    df = pd.DataFrame(detalGdict)
    df.to_csv(outfile, index=False)


def main():
    parser = argparse.ArgumentParser(description='GBSA Calculation.')
    parser.add_argument('-i', dest='receptor', help='Input protein file with pdb format.', required=True)
    parser.add_argument('-l', dest='ligand', help='Ligand files to calculate binding energy.', nargs='+', default=None)
    parser.add_argument('-c', dest='config', help='Configue file, default: %s'%DEFAULT_CONFIGURE_FILE, default=DEFAULT_CONFIGURE_FILE)
    parser.add_argument('-d', dest='ligdir', help='Floder contains many ligand files. file format: .mol or .sdf', default=None)
    parser.add_argument('-f', dest='pbsafile', help='gmx_MMPBSA input file. default=None', default=None)
    parser.add_argument('-o', dest='outfile', help='Output file.', default='BindingEnergy.csv')
    parser.add_argument('--mode', help='Calculation mode, use input file or minimization file or MD simulation file to calculate GBSA. default:None', choices=[None, 'input', 'em', 'md' ],default=None)
    parser.add_argument('--verbose', help='Keep all the files.', action='store_true', default=False)

    args = parser.parse_args()
    receptor, ligands, conf, ligdir, outfile, verbose = args.receptor, args.ligand, args.config, args.ligdir, args.outfile, args.verbose
    
    if ligands is None:
        ligands = []
    if ligdir:
        for fileName in os.listdir(ligdir):
            if fileName.endswith(('mol','sdf')):
                ligands.append(os.path.join(ligdir, fileName))
    if len(ligands)==0:
        raise Exception('No ligands file found.')

    if not os.path.exists(conf):
        raise Exception("Not found the configure file! %s"%conf)
    config = configparser.ConfigParser()
    config.read(conf)

    mmpbsafile = os.path.abspath(args.pbsafile) if args.pbsafile else args.pbsafile

    paras = {
        'simulation':{
            'mode': config.get('simulation', 'mode', fallback='em'),
            'boxtype' : config.get('simulation', 'boxtype', fallback='triclinic'),
            'boxsize' : config.getfloat('simulation', 'boxsize', fallback=0.9),
            'conc': config.getfloat('simulation', 'conc', fallback=0.15),
            'nsteps': config.getint('simulation', 'nsteps', fallback=500000),
            'nframe': config.getint('simulation', 'nframe', fallback=100),
            'eqsteps': config.getint('simulation', 'eqsteps', fallback=50000),
            'proteinforcefield': config.get('simulation', 'proteinforcefield', fallback='amber99sb-ildn'),
            'ligandforcefield': config.get('simulation', 'ligandforcefield', fallback='gaff2'),
            'maxsol': config.getint('simulation', 'maxsol', fallback=0),
        },
        'PBSA':  {k:v for k,v in config.items('PBSA')}
    }
    if args.mode:
        paras['simulation']['mode'] = args.mode

    if paras['simulation']['mode'] == 'em':
        minim_peipline(receptorfile=receptor, ligandfiles=ligands, paras=paras, outfile=outfile, mmpbsafile=mmpbsafile, verbose=verbose)
    elif paras['simulation']['mode'] == 'md':
        md_pipeline(receptorfile=receptor, ligandfiles=ligands, paras=paras, outfile=outfile, mmpbsafile=mmpbsafile, verbose=verbose)
    elif paras['simulation']['mode'] == 'input':
        base_pipeline(receptorfile=receptor, ligandfiles=ligands, paras=paras, outfile=outfile, mmpbsafile=mmpbsafile, verbose=verbose)

if __name__ == "__main__":
    main()
