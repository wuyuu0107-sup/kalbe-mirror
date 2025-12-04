"""
Base Profiler for Performance Testing

This module provides a base class for profiling Django application components.
Inspired by the scraper profiling pattern, adapted for Django services.
Uses cProfile for detailed profiling and custom timing for benchmarking.
"""

import time
import json
import cProfile
import pstats
import io
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from statistics import mean, median, stdev
import os


class BaseProfiler:
    """
    Base class for profiling application components.
    
    Provides core profiling functionality that can be extended
    for specific modules like user_settings, authentication, etc.
    """
    
    def __init__(self, module_name: str):
        """
        Initialize the profiler.
        
        Args:
            module_name: Name of the module being profiled (e.g., 'user_settings')
        """
        self.module_name = module_name
        self.results = {}
        self.cprofile_stats = {}
        self.ENV = self._load_environment()
        self._setup_vendor_specific()
    
    def _load_environment(self) -> Dict[str, str]:
        """Load environment variables from .env.profiling file"""
        env_file = Path(__file__).parent.parent / '.env.profiling'
        env_vars = {}
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, _, value = line.partition('=')
                        env_vars[key.strip()] = value.strip()
        
        # Override with actual environment variables
        env_vars.update(os.environ)
        return env_vars
    
    def _setup_vendor_specific(self):
        """
        Setup module-specific components and test data.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _setup_vendor_specific")
    
    def _profile_component(
        self,
        component_name: str,
        iterations: int,
        callback: Callable[[int], None],
        warmup: bool = True,
        use_cprofile: bool = False
    ) -> Dict[str, Any]:
        """
        Profile a component by running it multiple times.
        
        Args:
            component_name: Name of the component being profiled
            iterations: Number of times to run the component
            callback: Function to call for each iteration
            warmup: Whether to do a warmup run before profiling
            use_cprofile: Whether to use cProfile for detailed profiling
            
        Returns:
            Dictionary with profiling results including timings and statistics
        """
        times = []
        errors = []
        
        # Warmup run
        if warmup and iterations > 1:
            try:
                callback(0)
            except Exception as e:
                print(f"  Warmup error: {e}")
        
        # Setup cProfile if enabled
        profiler = None
        if use_cprofile:
            profiler = cProfile.Profile()
            profiler.enable()
        
        # Profile runs
        for i in range(iterations):
            start_time = time.perf_counter()
            try:
                callback(i)
                end_time = time.perf_counter()
                times.append(end_time - start_time)
            except Exception as e:
                end_time = time.perf_counter()
                times.append(end_time - start_time)
                errors.append(str(e))
                print(f"  Error in iteration {i + 1}: {e}")
        
        # Stop cProfile and save stats
        if profiler:
            profiler.disable()
            self.cprofile_stats[component_name] = profiler
        
        # Calculate statistics
        result = {
            'component': component_name,
            'iterations': iterations,
            'times': times,
            'total_time': sum(times),
            'avg_time': mean(times) if times else 0,
            'median_time': median(times) if times else 0,
            'min_time': min(times) if times else 0,
            'max_time': max(times) if times else 0,
            'std_dev': stdev(times) if len(times) > 1 else 0,
            'errors': errors,
            'error_count': len(errors),
            'success_rate': (iterations - len(errors)) / iterations * 100 if iterations > 0 else 0,
            'profiled_with_cprofile': use_cprofile
        }
        
        self.results[component_name] = result
        return result
    
    def _create_mock_html(
        self,
        product_class: str,
        product_link_class: str,
        price_class: str,
        base_price: int
    ) -> str:
        """
        Create mock HTML for testing HTML parsers.
        Can be overridden by subclasses if needed.
        """
        products = []
        for i in range(10):
            products.append(f'''
            <div class="{product_class}">
                <a href="/product-{i}" class="{product_link_class}">
                    <span>Test Product {i}</span>
                    <span class="{price_class}">Rp{base_price * (i + 1):,}</span>
                </a>
            </div>
            ''')
        
        return f'''
        <html>
            <body>
                <div class="container">
                    {''.join(products)}
                </div>
            </body>
        </html>
        '''
    
    def profile_component_with_data(
        self,
        component_name: str,
        component: Any,
        method_name: str,
        test_data: List[Any],
        iterations: int = None
    ) -> Dict[str, Any]:
        """
        Profile a component method with various test data.
        
        Args:
            component_name: Name for this profiling test
            component: The component instance to profile
            method_name: Name of the method to call
            test_data: List of data items to test with
            iterations: Number of iterations (defaults to ENV setting)
            
        Returns:
            Profiling results dictionary
        """
        if iterations is None:
            iterations = int(self.ENV.get('PROFILING_ITERATIONS_DEFAULT', '10'))
        
        print(f"Profiling {component_name} ({iterations} iterations)...")
        
        method = getattr(component, method_name)
        
        def callback(i):
            data = test_data[i % len(test_data)]
            try:
                result = method(data)
                return result
            except Exception as e:
                print(f"  Error with data {data}: {e}")
                raise
        
        result = self._profile_component(component_name, iterations, callback)
        return result
    
    def run_basic_profiling(self):
        """
        Run basic profiling tests.
        Should be implemented by subclasses to define what "basic" means.
        """
        raise NotImplementedError("Subclasses must implement run_basic_profiling")
    
    def generate_performance_report(self) -> Path:
        """
        Generate a detailed performance report.
        
        Returns:
            Path to the generated report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = Path(__file__).parent.parent / 'profiling_reports'
        report_dir.mkdir(exist_ok=True)
        
        report_file = report_dir / f'{self.module_name}_profile_{timestamp}.json'
        
        report_data = {
            'module': self.module_name,
            'timestamp': timestamp,
            'datetime': datetime.now().isoformat(),
            'environment': dict(self.ENV),
            'results': self.results,
            'summary': self._generate_summary()
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        # Generate cProfile reports if available
        if self.cprofile_stats:
            self._generate_cprofile_reports(report_dir, timestamp)
        
        return report_file
    
    def _generate_cprofile_reports(self, report_dir: Path, timestamp: str):
        """Generate detailed cProfile reports for profiled components"""
        cprofile_dir = report_dir / f'{self.module_name}_cprofile_{timestamp}'
        cprofile_dir.mkdir(exist_ok=True)
        
        for component_name, profiler in self.cprofile_stats.items():
            # Generate text report
            text_report_file = cprofile_dir / f'{component_name}.txt'
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            
            # Sort by cumulative time and print top functions
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.print_stats(50)  # Top 50 functions
            
            with open(text_report_file, 'w', encoding='utf-8') as f:
                f.write(f"cProfile Report for {component_name}\n")
                f.write("=" * 80 + "\n\n")
                f.write("Top 50 functions by cumulative time:\n")
                f.write("-" * 80 + "\n")
                f.write(stream.getvalue())
                
                # Add report sorted by total time
                stream = io.StringIO()
                stats = pstats.Stats(profiler, stream=stream)
                stats.strip_dirs()
                stats.sort_stats('tottime')
                stats.print_stats(50)
                
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("Top 50 functions by total time:\n")
                f.write("-" * 80 + "\n")
                f.write(stream.getvalue())
            
            # Generate binary stats file for later analysis
            stats_file = cprofile_dir / f'{component_name}.pstats'
            stats = pstats.Stats(profiler)
            stats.dump_stats(str(stats_file))
            
        print(f"\ncProfile reports saved to: {cprofile_dir}")
    
    def print_cprofile_summary(self, component_name: str, top_n: int = 10):
        """
        Print a summary of cProfile results for a specific component.
        
        Args:
            component_name: Name of the component to print stats for
            top_n: Number of top functions to display
        """
        if component_name not in self.cprofile_stats:
            print(f"No cProfile data available for {component_name}")
            return
        
        print(f"\n{'=' * 60}")
        print(f"cProfile Summary - {component_name}")
        print(f"{'=' * 60}\n")
        
        profiler = self.cprofile_stats[component_name]
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats(top_n)
        
        print(f"Top {top_n} functions by cumulative time:")
        print(stream.getvalue())
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of all profiling results"""
        if not self.results:
            return {}
        
        total_time = sum(r['total_time'] for r in self.results.values())
        total_iterations = sum(r['iterations'] for r in self.results.values())
        total_errors = sum(r['error_count'] for r in self.results.values())
        
        return {
            'total_components': len(self.results),
            'total_time': total_time,
            'total_iterations': total_iterations,
            'total_errors': total_errors,
            'overall_success_rate': (total_iterations - total_errors) / total_iterations * 100 if total_iterations > 0 else 0,
            'slowest_component': max(self.results.items(), key=lambda x: x[1]['avg_time'])[0] if self.results else None,
            'fastest_component': min(self.results.items(), key=lambda x: x[1]['avg_time'])[0] if self.results else None,
        }
    
    def print_performance_summary(self):
        """Print a formatted summary of profiling results"""
        print("\n" + "=" * 60)
        print(f"PERFORMANCE SUMMARY - {self.module_name.upper()}")
        print("=" * 60)
        
        if not self.results:
            print("No profiling results available")
            return
        
        summary = self._generate_summary()
        
        print(f"\nTotal Components Profiled: {summary['total_components']}")
        print(f"Total Time: {summary['total_time']:.4f}s")
        print(f"Total Iterations: {summary['total_iterations']}")
        print(f"Total Errors: {summary['total_errors']}")
        print(f"Overall Success Rate: {summary['overall_success_rate']:.2f}%")
        print(f"\nSlowest Component: {summary['slowest_component']}")
        print(f"Fastest Component: {summary['fastest_component']}")
        
        print("\n" + "-" * 60)
        print("DETAILED RESULTS")
        print("-" * 60)
        
        for name, result in self.results.items():
            print(f"\n{name}:")
            print(f"  Iterations: {result['iterations']}")
            print(f"  Average Time: {result['avg_time']:.4f}s")
            print(f"  Median Time: {result['median_time']:.4f}s")
            print(f"  Min Time: {result['min_time']:.4f}s")
            print(f"  Max Time: {result['max_time']:.4f}s")
            print(f"  Std Dev: {result['std_dev']:.4f}s")
            print(f"  Success Rate: {result['success_rate']:.2f}%")
            if result['errors']:
                print(f"  Errors: {result['error_count']}")
                for i, error in enumerate(result['errors'][:3], 1):
                    print(f"    {i}. {error}")
                if len(result['errors']) > 3:
                    print(f"    ... and {len(result['errors']) - 3} more errors")
