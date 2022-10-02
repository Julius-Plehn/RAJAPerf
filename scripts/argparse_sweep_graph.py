#!/usr/bin/env python3
import argparse
import sys
import os
import csv
import glob
import difflib

def get_size_from_dir_name(sweep_subdir_name):
   # print(sweep_subdir_name)
   run_size_name = sweep_subdir_name.replace("SIZE_", "")
   try:
      run_size = int(run_size_name)
      return str(run_size)
   except ValueError:
      raise NameError("Expected SIZE_<run_size>".format(sweep_subdir_name))

def get_close_matches(test_value,match_values) -> list:
   close_matches = difflib.get_close_matches(test_value,match_values, n=30, cutoff=0.25)
   if len(close_matches) > 0:
      # cull for substring
      found_sub = []
      for mm in close_matches:
         if mm.find(test_value) != -1:
            found_sub.append(mm)
      if len(found_sub) > 0:
         close_matches = found_sub
   return close_matches

def direct_action_check(values,prescan_dict_name, namespace):
   check = []
   for k in values:
      if k in namespace.prescan[prescan_dict_name]:
         check.append(k)
      else:
         close_matches = get_close_matches(k, namespace.prescan[prescan_dict_name])
         if len(close_matches) > 0:
            raise NameError("Invalid {0} check for {1}: Did you mean one of {2}, or try changing case".format(prescan_dict_name, k, str(close_matches)))
         else:
            raise NameError("Invalid {0} check for {1}: Use one of {2}".format(prescan_dict_name, k, str(namespace.prescan[prescan_dict_name])))
   return check
  
def close_action_check(values,prescan_dict_name, namespace):
   outer_set = set()
   for k in values:
      inner_check = set()
      if k in namespace.prescan[prescan_dict_name]:
         inner_check.add(k)
      else:
         close_matches = get_close_matches(k, namespace.prescan[prescan_dict_name])
         if len(close_matches) > 0:
            inner_check.update(close_matches)
      if len(inner_check) == 0:
         raise NameError("Invalid close check against {0} for {1}: Use something close to any of {2}, or try changing case".format(prescan_dict_name,k, str(namespace.prescan[prescan_dict_name])))
      outer_set.update(inner_check)
   check = list(outer_set)
   check.sort()
   return check

class process_argparse():
   # the intended use is to return both an args object for Namespace,
   # and unknown args that specifically do not use - or -- prefix
   class KernelAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         check = direct_action_check(values,"kernels_union",namespace)
         setattr(namespace, self.dest, check)

   class KernelCloseAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         check = close_action_check(values,"kernels_union",namespace)
         setattr(namespace, self.dest, check)
   class VariantAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         check = direct_action_check(values, "variants", namespace)
         setattr(namespace, self.dest, check)

   class VariantCloseAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         check = close_action_check(values, "variants", namespace)
         setattr(namespace, self.dest, check)

   class TuningAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         check = direct_action_check(values, "tunings", namespace)
         setattr(namespace, self.dest, check)

   class TuningCloseAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         check = close_action_check(values, "tunings", namespace)
         setattr(namespace, self.dest, check)

   class DirectoryAction(argparse.Action):
      def __init__(self, option_strings, dest, nargs='+', **kwargs):
         if nargs != '+':
            raise ValueError("Expected variable nargs to be set to '+'")
         super().__init__(option_strings, dest, nargs, **kwargs)
   
      def __call__(self, parser, namespace, values, option_string=None):
         # print('Action Namespace=%r values=%r option_string=%r' % (namespace, values, option_string))
         prescan = self.prescan_sweep_dirs(values)
         setattr(namespace, 'prescan', prescan)
         setattr(namespace, self.dest, prescan["directories"])  # do the normal attr set for dest

      def prescan_sweep_dirs(self,sweep_dir_paths) -> dict:
         prescan = {"directories": [],"kernels_union": [], "kernels_intersection": [], "variants": [], "tunings": [], "sweep_sizes": [],
                    "machines"     : []}
         # machines only gleans os.path.basename of sweep_dir_paths, and does not actually parse real encoded machine names from data; so machine_name is a convention for directory naming
         sets = []
         outer_runsizes_set = set()
         for sweep_dir_path in sweep_dir_paths:
            if not os.path.exists(sweep_dir_path):
               raise NameError("Invalid directory: {0}".format(sweep_dir_path))
            kernel_set = set()
            sweep_dir_path = sweep_dir_path.rstrip(os.sep)
            prescan["directories"].append(sweep_dir_path)
            sweep_dir_name = os.path.basename(sweep_dir_path)
            if sweep_dir_name not in prescan["machines"]:
               prescan["machines"].append(sweep_dir_name)
            subdirs = sorted(glob.glob(glob.escape(sweep_dir_path) + os.sep + "**" + os.sep + "SIZE_*", recursive=True))
            inner_runsizes_set = set()
            for subdir in subdirs:
               # print(subdir)
               run_size = get_size_from_dir_name(os.path.basename(subdir))
               inner_runsizes_set.add(run_size)
               #if run_size not in prescan["sweep_sizes"]:
               #   prescan["sweep_sizes"].append(run_size)
               # open one of the timing files at this run_size
               timing_files = sorted(glob.glob(glob.escape(subdir) + os.sep + "RAJAPerf-timing-*", recursive=False))
               with open(timing_files[0], "r") as file:
                  file_reader = csv.reader(file, delimiter=',')
                  variants_read = False
                  tunings_read = False
                  for row in file_reader:
                     # print(row)
                     if row[0].strip() == "Kernel":
                        if not variants_read:
                           for c in range(1, len(row)):
                              variant_name = row[c].strip()
                              if variant_name not in prescan["variants"]:
                                 prescan["variants"].append(variant_name)
                           variants_read = True
                        elif not tunings_read:
                           for c in range(1, len(row)):
                              tuning_name = row[c].strip()
                              if tuning_name not in prescan["tunings"]:
                                 prescan["tunings"].append(tuning_name)
                           tunings_read = True
                     elif variants_read == True & tunings_read == True:
                        kernel_name = row[0].strip()
                        if kernel_name not in prescan["kernels_union"]:
                           prescan["kernels_union"].append(kernel_name)
                        if kernel_name not in kernel_set:
                           kernel_set.add(kernel_name)
            if (not outer_runsizes_set) and inner_runsizes_set:
               outer_runsizes_set = inner_runsizes_set
            outer_runsizes_set = outer_runsizes_set.intersection(inner_runsizes_set)
            sets.append(kernel_set)
         prescan["kernels_intersection"] = set.intersection(*sets)
         prescan["sweep_sizes"] = list(outer_runsizes_set)
         return prescan
      
   

   def __init__(self):
      self.parent_parser = argparse.ArgumentParser(add_help=False)
      self.parent_parser.add_argument('-d','--directories', required=True, nargs='+', action=self.DirectoryAction)
      self.child_parser = argparse.ArgumentParser(parents=[self.parent_parser])
      
      self.child_parser.add_argument('-o','--output',nargs=1,
                                     help="output file prefix")
      self.child_parser.add_argument('-gname', '--graph-name', nargs=1,
                                     help="graph name")
      self.child_parser.add_argument('-lloc', '--legend-location', nargs=2,
                                     help="legend location x y ")
      self.child_parser.add_argument('-ylabel', '--y-axis-label', nargs=1,
                                     help="y axis label")
      self.child_parser.add_argument('-yscale', '--y-axis-scale', nargs=1,
                                     help="y axis scale")
      self.child_parser.add_argument('-xlabel', '--x-axis-label', nargs=1,
                                     help="x axis label")
      self.child_parser.add_argument('-xscale', '--x-axis-scale', nargs=1,
                                     help="x axis scale")
      self.child_parser.add_argument('-hbin', '--histogram-bin-size', nargs=1,
                                     help="histogram bin size")
      self.child_parser.add_argument('-ylim', '--y-axis-limit', nargs=2,
                                     help="y axis limit")
      self.child_parser.add_argument('-xlim', '--x-axis-limit', nargs=2,
                                     help="x axis limit")
      self.child_parser.add_argument('--recolor', nargs=4,
                                     help="recolor series_name r g b")
      self.child_parser.add_argument('--reformat', nargs=2,
                                     help="reformat series_name format_str")
      #the following should be modified to use action based on possible kinds
      self.child_parser.add_argument('-p','--print', nargs=1,
                                     help="print one of kind argument expression")
      self.child_parser.add_argument('-slg','--split-line-graphs', nargs=1,
                                     help="split line graph of one kind argument expression")
      self.child_parser.add_argument('-bg','--bar-graph', nargs=1,
                                     help="bar graph of one kind argument expression")
      self.child_parser.add_argument('-hg','--histogram-graph', nargs=1,
                                     help="histogram graph of one kind argument expression")
      
      self.child_parser.add_argument('-k', '--kernels', nargs='+', action=self.KernelAction,
                                     help='kernels to include')
      self.child_parser.add_argument('-ek', '--exclude-kernels', nargs='+', action=self.KernelAction,
                                     help='kernels to exclude')
      self.child_parser.add_argument('-kc', '--kernels-close', nargs='+', action=self.KernelCloseAction,
                                     help="search for set of kernels to include close to arg eg. Poly_ Basic_ etc")
      self.child_parser.add_argument('-ekc', '--exclude-kernels-close', nargs='+', action=self.KernelCloseAction,
                                     help="search for set of kernels to exclude close to arg eg. Poly_ Basic_ etc")

      self.child_parser.add_argument('-v', '--variants', nargs='+', action=self.VariantAction,
                                     help='variants to include')
      self.child_parser.add_argument('-ev', '--exclude-variants', nargs='+', action=self.VariantAction,
                                     help='variants to exclude')
      self.child_parser.add_argument('-vc', '--variants-close', nargs='+', action=self.VariantCloseAction,
                                     help="search for set of variants to include close to arg like Seq, CUDA, HIP, etc")
      self.child_parser.add_argument('-evc', '--exclude-variants-close', nargs='+', action=self.VariantCloseAction,
                                     help="search for set of variants to exclude close to arg like Seq, CUDA, HIP etc")

      self.child_parser.add_argument('-t', '--tunings', nargs='+', action=self.TuningAction,
                                     help='tunings to include')
      self.child_parser.add_argument('-et', '--exclude-tunings', nargs='+', action=self.TuningAction,
                                     help='tunings to exclude')
      self.child_parser.add_argument('-tc', '--tunings-close', nargs='+', action=self.TuningCloseAction,
                                     help="search for set of tunings to include close to arg eg. block, def{ault} etc")
      self.child_parser.add_argument('-etc', '--exclude-tunings-close', nargs='+', action=self.TuningCloseAction,
                                     help="search for set of tunings to exclude close to arg eg. block, def{ault} etc")
      
      
   
   def parse_args(self,argv):
      args, unknown = self.child_parser.parse_known_args(argv)
      return args, unknown
      
def main(argv):
  first_stage_parser = process_argparse()
  args, unknown = first_stage_parser.parse_args(argv)
  print(args)
  print(unknown)

if __name__ == '__main__':
   main(sys.argv[1:])