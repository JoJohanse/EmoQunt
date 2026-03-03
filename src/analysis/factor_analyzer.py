import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.preprocessing import StandardScaler, RobustScaler
import warnings
from typing import Dict, List, Tuple, Optional, Union
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings('ignore')

class FactorPreprocessor:
    """
    因子预处理器
    """
    
    def __init__(self):
        """
        初始化预处理器
        """
        self.scalers = {}
        self.industry_mapping = None
        self.market_cap_data = None
    
    def winsorize(self, factor_data: pd.DataFrame, limits: Tuple[float, float] = (0.025, 0.025)) -> pd.DataFrame:
        """
        Winsorize去极值处理
        :param factor_data: 因子数据，索引为日期，列为股票代码
        :param limits: 去极值的上下限比例 (下限, 上限)
        :return: 去极值后的因子数据
        """
        processed_data = factor_data.copy()
        
        for date in factor_data.index:
            # 获取当天的因子值
            daily_factors = factor_data.loc[date].dropna()
            
            if len(daily_factors) == 0:
                continue
            
            # 计算分位数
            lower_q = daily_factors.quantile(limits[0])
            upper_q = daily_factors.quantile(1 - limits[1])
            
            # 应用winsorize
            processed_data.loc[date] = daily_factors.clip(lower=lower_q, upper=upper_q)
        
        return processed_data
    
    def z_score_normalize(self, factor_data: pd.DataFrame, method: str = 'standard') -> pd.DataFrame:
        """
        Z-score标准化
        :param factor_data: 因子数据
        :param method: 标准化方法 ('standard', 'robust')
        :return: 标准化后的因子数据
        """
        processed_data = factor_data.copy()
        
        for date in factor_data.index:
            # 获取当天的因子值
            daily_factors = factor_data.loc[date].dropna()
            
            if len(daily_factors) == 0:
                continue
            
            if method == 'standard':
                # 使用StandardScaler
                scaler = StandardScaler()
                normalized_values = scaler.fit_transform(daily_factors.values.reshape(-1, 1)).flatten()
            elif method == 'robust':
                # 使用RobustScaler（对异常值更鲁棒）
                scaler = RobustScaler()
                normalized_values = scaler.fit_transform(daily_factors.values.reshape(-1, 1)).flatten()
            else:
                # 手动计算Z-score
                mean_val = daily_factors.mean()
                std_val = daily_factors.std()
                if std_val != 0:
                    normalized_values = (daily_factors - mean_val) / std_val
                else:
                    normalized_values = daily_factors - mean_val  # 如果标准差为0，只减去均值
            
            # 更新处理后的值
            processed_data.loc[date, daily_factors.index] = normalized_values
        
        return processed_data
    
    def neutralize_by_group(
        self, 
        factor_data: pd.DataFrame, 
        group_data: pd.DataFrame,
        weights: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        按组别进行中性化处理（如行业、市值分组）
        :param factor_data: 因子数据
        :param group_data: 分组数据（如行业、市值）
        :param weights: 权重数据（可选）
        :return: 中性化后的因子数据
        """
        processed_data = factor_data.copy()
        
        for date in factor_data.index:
            if date not in group_data.index:
                continue
                
            # 获取当天的因子和分组数据
            daily_factors = factor_data.loc[date].dropna()
            daily_groups = group_data.loc[date].dropna()
            
            # 取交集
            common_stocks = daily_factors.index.intersection(daily_groups.index)
            if len(common_stocks) == 0:
                continue
            
            factors_aligned = daily_factors[common_stocks]
            groups_aligned = daily_groups[common_stocks]
            
            # 按组别进行中性化
            for group in groups_aligned.unique():
                group_stocks = groups_aligned[groups_aligned == group].index
                if len(group_stocks) <= 1:  # 组内股票太少无法回归
                    continue
                
                group_factors = factors_aligned[group_stocks]
                
                # 计算组内均值
                group_mean = group_factors.mean()
                
                # 从因子值中减去组内均值
                processed_data.loc[date, group_stocks] = group_factors - group_mean
        
        return processed_data
    
    def neutralize_by_market_cap(
        self, 
        factor_data: pd.DataFrame, 
        market_cap_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        按市值进行中性化处理
        :param factor_data: 因子数据
        :param market_cap_data: 市值数据
        :return: 市值中性化后的因子数据
        """
        processed_data = factor_data.copy()
        
        for date in factor_data.index:
            if date not in market_cap_data.index:
                continue
                
            # 获取当天的因子和市值数据
            daily_factors = factor_data.loc[date].dropna()
            daily_mcap = market_cap_data.loc[date].dropna()
            
            # 取交集
            common_stocks = daily_factors.index.intersection(daily_mcap.index)
            if len(common_stocks) < 2:  # 至少需要2个点进行回归
                continue
            
            factors_aligned = daily_factors[common_stocks]
            mcap_aligned = daily_mcap[common_stocks]
            
            # 对数化市值
            log_mcap = np.log(mcap_aligned)
            
            # 线性回归：因子 ~ 市值
            # y = factor, x = log(market_cap)
            slope, intercept, r_value, p_value, std_err = stats.linregress(log_mcap, factors_aligned)
            
            # 计算残差（去除市值影响后的因子）
            predicted = slope * log_mcap + intercept
            residuals = factors_aligned - predicted
            
            # 更新处理后的因子值
            processed_data.loc[date, common_stocks] = residuals
        
        return processed_data
    
    def neutralize_by_industry(
        self, 
        factor_data: pd.DataFrame, 
        industry_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        按行业进行中性化处理
        :param factor_data: 因子数据
        :param industry_data: 行业数据
        :return: 行业中性化后的因子数据
        """
        return self.neutralize_by_group(factor_data, industry_data)
    
    def orthogonalize_factors(
        self, 
        target_factor: pd.DataFrame, 
        reference_factors: List[pd.DataFrame]
    ) -> pd.DataFrame:
        """
        对目标因子进行正交化处理（去除参考因子的影响）
        :param target_factor: 目标因子
        :param reference_factors: 参考因子列表
        :return: 正交化后的目标因子
        """
        processed_data = target_factor.copy()
        
        for date in target_factor.index:
            # 检查所有参考因子是否都有当天数据
            valid_reference_data = []
            for ref_factor in reference_factors:
                if date in ref_factor.index:
                    valid_reference_data.append(ref_factor.loc[date].dropna())
                else:
                    continue
            
            if len(valid_reference_data) == 0:
                continue
            
            # 获取目标因子当天数据
            target_daily = target_factor.loc[date].dropna()
            
            # 找到所有因子的共同股票
            common_stocks = target_daily.index
            for ref_data in valid_reference_data:
                common_stocks = common_stocks.intersection(ref_data.index)
            
            if len(common_stocks) < len(valid_reference_data) + 1:  # 至少要有足够的自由度
                continue
            
            # 对齐数据
            y = target_daily[common_stocks].values
            X = np.column_stack([ref_data[common_stocks].values for ref_data in valid_reference_data])
            
            # 多元线性回归
            try:
                # 计算回归系数 (X'X)^(-1)X'y
                XtX_inv = np.linalg.inv(X.T @ X)
                coef = XtX_inv @ X.T @ y
                
                # 计算预测值
                y_pred = X @ coef
                
                # 计算残差（正交化后的因子）
                residuals = y - y_pred
                
                # 更新处理后的因子值
                processed_data.loc[date, common_stocks] = residuals
            except np.linalg.LinAlgError:
                # 如果矩阵不可逆，跳过正交化
                continue
        
        return processed_data
    
    def rank_transform(self, factor_data: pd.DataFrame) -> pd.DataFrame:
        """
        排序变换
        :param factor_data: 因子数据
        :return: 排序变换后的因子数据
        """
        processed_data = factor_data.copy()
        
        for date in factor_data.index:
            daily_factors = factor_data.loc[date].dropna()
            
            if len(daily_factors) == 0:
                continue
            
            # 计算排序
            ranks = daily_factors.rank(method='average')
            
            # 转换为标准正态分布（ICDF变换）
            # 将排序归一化到(0,1)区间，然后应用标准正态分布的反函数
            normalized_ranks = (ranks - 0.5) / len(ranks)
            rank_norm = stats.norm.ppf(normalized_ranks.clip(0.001, 0.999))  # 避免边界值
            
            processed_data.loc[date, daily_factors.index] = rank_norm
        
        return processed_data
    
    def industry_dummy_neutralize(
        self, 
        factor_data: pd.DataFrame, 
        industry_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        使用行业哑变量进行中性化
        :param factor_data: 因子数据
        :param industry_data: 行业数据
        :return: 行业哑变量中性化后的因子数据
        """
        processed_data = factor_data.copy()
        
        for date in factor_data.index:
            if date not in industry_data.index:
                continue
                
            # 获取当天数据
            daily_factors = factor_data.loc[date].dropna()
            daily_industry = industry_data.loc[date].dropna()
            
            # 取交集
            common_stocks = daily_factors.index.intersection(daily_industry.index)
            if len(common_stocks) < 2:
                continue
            
            factors_aligned = daily_factors[common_stocks]
            industry_aligned = daily_industry[common_stocks]
            
            # 创建行业哑变量
            unique_industries = industry_aligned.unique()
            if len(unique_industries) <= 1:
                continue
            
            # 为每个行业创建哑变量（排除最后一个作为参照组）
            X = np.zeros((len(common_stocks), len(unique_industries) - 1))
            industry_list = unique_industries[:-1]  # 排除最后一个作为参照
            
            for i, industry in enumerate(industry_list):
                X[:, i] = (industry_aligned == industry).astype(int)
            
            # 执行回归
            try:
                if X.shape[1] == 0:
                    continue
                    
                # 计算回归系数
                XtX_inv = np.linalg.inv(X.T @ X)
                coef = XtX_inv @ X.T @ factors_aligned.values
                
                # 计算预测值
                y_pred = X @ coef
                
                # 计算残差
                residuals = factors_aligned.values - y_pred
                
                # 更新处理后的因子值
                processed_data.loc[date, common_stocks] = residuals
            except np.linalg.LinAlgError:
                # 如果矩阵不可逆，跳过
                continue
        
        return processed_data
    
    def process_factor(
        self, 
        factor_data: pd.DataFrame,
        winsorize: bool = True,
        winsorize_limits: Tuple[float, float] = (0.025, 0.025),
        normalize: bool = True,
        normalize_method: str = 'standard',
        neutralize_industry: bool = False,
        industry_data: Optional[pd.DataFrame] = None,
        neutralize_market_cap: bool = False,
        market_cap_data: Optional[pd.DataFrame] = None,
        rank_transform_flag: bool = False
    ) -> pd.DataFrame:
        """
        完整的因子处理流程
        :param factor_data: 因子数据
        :param winsorize: 是否进行去极值
        :param winsorize_limits: 去极值上下限
        :param normalize: 是否进行标准化
        :param normalize_method: 标准化方法
        :param neutralize_industry: 是否进行行业中性化
        :param industry_data: 行业数据
        :param neutralize_market_cap: 是否进行市值中性化
        :param market_cap_data: 市值数据
        :param rank_transform_flag: 是否进行排序变换
        :return: 处理后的因子数据
        """
        processed = factor_data.copy()
        
        # 1. 去极值
        if winsorize:
            processed = self.winsorize(processed, winsorize_limits)
            print(f"✓ 完成去极值处理")
        
        # 2. 行业中性化
        if neutralize_industry and industry_data is not None:
            processed = self.neutralize_by_industry(processed, industry_data)
            print(f"✓ 完成行业中性化处理")
        
        # 3. 市值中性化
        if neutralize_market_cap and market_cap_data is not None:
            processed = self.neutralize_by_market_cap(processed, market_cap_data)
            print(f"✓ 完成市值中性化处理")
        
        # 4. 标准化
        if normalize:
            processed = self.z_score_normalize(processed, normalize_method)
            print(f"✓ 完成标准化处理")
        
        # 5. 排序变换
        if rank_transform_flag:
            processed = self.rank_transform(processed)
            print(f"✓ 完成排序变换")
        
        return processed

class FactorAnalyzer:
    """
    因子分析器
    """
    
    def __init__(self, factor_data: pd.DataFrame, forward_returns: pd.DataFrame = None):
        """
        初始化因子分析器
        :param factor_data: 因子数据，索引为日期，列为股票代码，值为因子值
        :param forward_returns: 未来收益率数据，索引为日期，列为股票代码，值为未来收益率
        """
        self.factor_data = factor_data
        self.forward_returns = forward_returns
        self.ic_series = None
        self.rank_ic_series = None
    
    def calculate_ic(self, method: str = 'pearson') -> pd.Series:
        """
        计算信息系数（IC）
        :param method: 相关系数计算方法 ('pearson', 'spearman')
        :return: IC 时间序列
        """
        ic_list = []
        dates = []
        
        for date in self.factor_data.index:
            if date in self.forward_returns.index:
                # 获取当天的因子值和未来收益率
                factor_values = self.factor_data.loc[date].dropna()
                return_values = self.forward_returns.loc[date].dropna()
                
                # 取交集
                common_stocks = factor_values.index.intersection(return_values.index)
                if len(common_stocks) < 2:  # 至少需要2个数据点才能计算相关性
                    continue
                
                factor_aligned = factor_values[common_stocks]
                returns_aligned = return_values[common_stocks]
                
                # 计算相关系数
                if method == 'pearson':
                    correlation = np.corrcoef(factor_aligned, returns_aligned)[0, 1]
                elif method == 'spearman':
                    correlation = stats.spearmanr(factor_aligned, returns_aligned)[0]
                else:
                    raise ValueError("method 必须是 'pearson' 或 'spearman'")
                
                if not np.isnan(correlation):
                    ic_list.append(correlation)
                    dates.append(date)
        
        self.ic_series = pd.Series(ic_list, index=dates, name='IC')
        return self.ic_series
    
    def calculate_rank_ic(self) -> pd.Series:
        """
        计算秩信息系数（Rank IC）
        :return: Rank IC 时间序列
        """
        rank_ic_list = []
        dates = []
        
        for date in self.factor_data.index:
            if date in self.forward_returns.index:
                # 获取当天的因子值和未来收益率
                factor_values = self.factor_data.loc[date].dropna()
                return_values = self.forward_returns.loc[date].dropna()
                
                # 取交集
                common_stocks = factor_values.index.intersection(return_values.index)
                if len(common_stocks) < 2:
                    continue
                
                factor_aligned = factor_values[common_stocks]
                returns_aligned = return_values[common_stocks]
                
                # 计算秩相关系数（spearman）
                rank_corr = stats.spearmanr(factor_aligned, returns_aligned)[0]
                
                if not np.isnan(rank_corr):
                    rank_ic_list.append(rank_corr)
                    dates.append(date)
        
        self.rank_ic_series = pd.Series(rank_ic_list, index=dates, name='Rank_IC')
        return self.rank_ic_series
    
    def calculate_ic_stats(self) -> Dict:
        """
        计算IC统计指标
        :return: IC统计指标字典
        """
        if self.ic_series is None:
            self.calculate_ic()
        
        if self.rank_ic_series is None:
            self.calculate_rank_ic()
        
        stats_dict = {}
        
        # IC均值
        stats_dict['ic_mean'] = self.ic_series.mean()
        stats_dict['rank_ic_mean'] = self.rank_ic_series.mean()
        
        # IC标准差
        stats_dict['ic_std'] = self.ic_series.std()
        stats_dict['rank_ic_std'] = self.rank_ic_series.std()
        
        # ICIR (Information Coefficient Information Ratio)
        stats_dict['ic_ir'] = self.ic_series.mean() / self.ic_series.std() if self.ic_series.std() != 0 else 0
        stats_dict['rank_ic_ir'] = self.rank_ic_series.mean() / self.rank_ic_series.std() if self.rank_ic_series.std() != 0 else 0
        
        # IC胜率（绝对值大于0的比例）
        stats_dict['ic_win_rate'] = (self.ic_series.abs() > 0).mean()
        stats_dict['rank_ic_win_rate'] = (self.rank_ic_series.abs() > 0).mean()
        
        # IC大于0的比例
        stats_dict['ic_positive_rate'] = (self.ic_series > 0).mean()
        stats_dict['rank_ic_positive_rate'] = (self.rank_ic_series > 0).mean()
        
        # 最大回撤（IC序列的）
        ic_cumprod = (1 + self.ic_series.fillna(0)).cumprod()
        ic_running_max = ic_cumprod.expanding().max()
        ic_drawdown = (ic_cumprod - ic_running_max) / ic_running_max
        stats_dict['ic_max_drawdown'] = ic_drawdown.min()
        
        return stats_dict
    
    def calculate_autocorrelation(self, lags: List[int] = [1, 5, 10, 20]) -> Dict:
        """
        计算因子自相关性
        :param lags: 滞后期列表
        :return: 自相关系数字典
        """
        autocorr_dict = {}
        
        # 对每个股票计算自相关性，然后取平均
        for lag in lags:
            correlations = []
            for stock in self.factor_data.columns:
                series = self.factor_data[stock].dropna()
                if len(series) > lag:
                    corr = series.corr(series.shift(lag))
                    if not np.isnan(corr):
                        correlations.append(corr)
            
            autocorr_dict[f'autocorr_lag_{lag}'] = np.mean(correlations) if correlations else np.nan
        
        return autocorr_dict
    
    def quantile_analysis(self, n_quantiles: int = 5) -> Dict:
        """
        因子分层分析
        :param n_quantiles: 分层数
        :return: 分层分析结果
        """
        results = {}
        
        # 按日期进行分层分析
        quantile_returns = {f'q{i+1}': [] for i in range(n_quantiles)}
        dates = []
        
        for date in self.factor_data.index:
            if date in self.forward_returns.index:
                # 获取当天的因子值和未来收益率
                factor_values = self.factor_data.loc[date].dropna()
                return_values = self.forward_returns.loc[date].dropna()
                
                # 取交集
                common_stocks = factor_values.index.intersection(return_values.index)
                if len(common_stocks) < n_quantiles:  # 至少需要n_quantiles个数据点
                    continue
                
                factor_aligned = factor_values[common_stocks]
                returns_aligned = return_values[common_stocks]
                
                # 按因子值分层
                quantile_labels = pd.qcut(factor_aligned, q=n_quantiles, labels=False, duplicates='drop')
                
                # 计算每层的平均收益率
                for i in range(n_quantiles):
                    stocks_in_quantile = quantile_labels[quantile_labels == i].index
                    if len(stocks_in_quantile) > 0:
                        avg_return = returns_aligned[stocks_in_quantile].mean()
                        quantile_returns[f'q{i+1}'].append(avg_return)
                    else:
                        quantile_returns[f'q{i+1}'].append(np.nan)
                
                dates.append(date)
        
        # 转换为DataFrame
        quantile_returns_df = pd.DataFrame(quantile_returns, index=dates)
        results['quantile_returns'] = quantile_returns_df
        
        # 计算多空组合收益（最高层 - 最底层）
        results['long_short_returns'] = quantile_returns_df['q1'] - quantile_returns_df[f'q{n_quantiles}']
        
        # 计算分层统计
        quantile_stats = {}
        for col in quantile_returns_df.columns:
            returns_series = quantile_returns_df[col].dropna()
            if len(returns_series) > 0:
                quantile_stats[col] = {
                    'mean_return': returns_series.mean(),
                    'std_return': returns_series.std(),
                    'sharpe_ratio': returns_series.mean() / returns_series.std() if returns_series.std() != 0 else 0,
                    'win_rate': (returns_series > 0).mean()
                }
        
        results['quantile_stats'] = quantile_stats
        results['long_short_stats'] = {
            'mean_return': results['long_short_returns'].mean(),
            'std_return': results['long_short_returns'].std(),
            'sharpe_ratio': results['long_short_returns'].mean() / results['long_short_returns'].std() if results['long_short_returns'].std() != 0 else 0,
            'win_rate': (results['long_short_returns'] > 0).mean()
        }
        
        return results
    
    def turnover_analysis(self, n_quantiles: int = 5) -> Dict:
        """
        换手率分析
        :param n_quantiles: 分层数
        :return: 换手率分析结果
        """
        turnover_dict = {}
        
        # 计算每层的换手率
        for q in range(1, n_quantiles + 1):
            quantile_turnovers = []
            
            for i in range(1, len(self.factor_data)):
                prev_date = self.factor_data.index[i-1]
                curr_date = self.factor_data.index[i]
                
                if prev_date in self.factor_data.index and curr_date in self.factor_data.index:
                    # 获取前一期和当期的因子数据
                    prev_factors = self.factor_data.loc[prev_date].dropna()
                    curr_factors = self.factor_data.loc[curr_date].dropna()
                    
                    # 取交集
                    common_stocks = prev_factors.index.intersection(curr_factors.index)
                    if len(common_stocks) < n_quantiles:
                        continue
                    
                    prev_aligned = prev_factors[common_stocks]
                    curr_aligned = curr_factors[common_stocks]
                    
                    # 按前一期因子值分层
                    prev_quantile_labels = pd.qcut(prev_aligned, q=n_quantiles, labels=False, duplicates='drop')
                    curr_quantile_labels = pd.qcut(curr_aligned, q=n_quantiles, labels=False, duplicates='drop')
                    
                    # 计算第q层的换手率
                    prev_q_stocks = set(prev_quantile_labels[prev_quantile_labels == q-1].index)
                    curr_q_stocks = set(curr_quantile_labels[curr_quantile_labels == q-1].index)
                    
                    if len(prev_q_stocks) > 0:
                        turnover = len(prev_q_stocks.intersection(curr_q_stocks)) / len(prev_q_stocks)
                        quantile_turnovers.append(1 - turnover)  # 换手率 = 1 - 保留率
                    else:
                        quantile_turnovers.append(np.nan)
            
            turnover_dict[f'quantile_{q}_turnover'] = np.nanmean(quantile_turnovers) if quantile_turnovers else np.nan
        
        return turnover_dict
    
    def factor_monotonicity(self, n_quantiles: int = 5) -> Dict:
        """
        因子单调性检验
        :param n_quantiles: 分层数
        :return: 单调性检验结果
        """
        # 先做分层分析
        quantile_results = self.quantile_analysis(n_quantiles)
        quantile_returns = quantile_results['quantile_returns']
        
        # 计算相邻层之间的收益差异
        monotonicity_dict = {}
        
        # 检查是否呈现单调趋势
        mean_returns = [quantile_returns[f'q{i+1}'].mean() for i in range(n_quantiles)]
        monotonicity_dict['mean_returns_by_quantile'] = mean_returns
        
        # 计算相邻层收益差
        adjacent_diffs = [mean_returns[i+1] - mean_returns[i] for i in range(n_quantiles-1)]
        monotonicity_dict['adjacent_diffs'] = adjacent_diffs
        
        # 计算单调性比例（相邻差值符号一致的比例）
        positive_diffs = [d for d in adjacent_diffs if d > 0]
        negative_diffs = [d for d in adjacent_diffs if d < 0]
        
        if len(adjacent_diffs) > 0:
            if len(positive_diffs) == len(adjacent_diffs) or len(negative_diffs) == len(adjacent_diffs):
                monotonicity_dict['monotonic'] = True
                monotonicity_dict['monotonicity_ratio'] = 1.0
            else:
                monotonicity_dict['monotonic'] = False
                monotonicity_dict['monotonicity_ratio'] = max(len(positive_diffs), len(negative_diffs)) / len(adjacent_diffs)
        else:
            monotonicity_dict['monotonic'] = False
            monotonicity_dict['monotonicity_ratio'] = 0.0
        
        return monotonicity_dict
    
    def generate_factor_report(self) -> Dict:
        """
        生成因子综合报告
        :return: 因子综合报告
        """
        report = {}
        
        # IC分析
        report['ic_analysis'] = self.calculate_ic_stats()
        
        # 自相关性分析
        report['autocorrelation_analysis'] = self.calculate_autocorrelation()
        
        # 分层分析
        report['quantile_analysis'] = self.quantile_analysis()
        
        # 换手率分析
        report['turnover_analysis'] = self.turnover_analysis()
        
        # 单调性分析
        report['monotonicity_analysis'] = self.factor_monotonicity()
        
        return report
    
    def plot_factor_analysis(self, figsize: Tuple[int, int] = (16, 12)):
        """
        绘制因子分析图表
        :param figsize: 图表大小
        """
        fig, axes = plt.subplots(2, 3, figsize=figsize)
        
        # 1. IC时间序列
        if self.ic_series is None:
            self.calculate_ic()
        axes[0, 0].plot(self.ic_series.index, self.ic_series.values, label='IC', alpha=0.7)
        axes[0, 0].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        axes[0, 0].set_title('IC 时间序列')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. IC分布直方图
        axes[0, 1].hist(self.ic_series.dropna(), bins=30, density=True, alpha=0.7, edgecolor='black')
        axes[0, 1].set_title('IC 分布直方图')
        axes[0, 1].axvline(x=self.ic_series.mean(), color='red', linestyle='--', label=f'Mean: {self.ic_series.mean():.3f}')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. 分层收益率
        quantile_results = self.quantile_analysis()
        quantile_returns = quantile_results['quantile_returns']
        for col in quantile_returns.columns:
            axes[0, 2].plot(quantile_returns.index, (1 + quantile_returns[col]).cumprod(), label=col)
        axes[0, 2].set_title('分层累计收益率')
        axes[0, 2].legend()
        axes[0, 2].grid(True, alpha=0.3)
        
        # 4. 多空组合收益率
        long_short_returns = quantile_results['long_short_returns']
        cumulative_ls = (1 + long_short_returns).cumprod()
        axes[1, 0].plot(long_short_returns.index, cumulative_ls, label='多空组合', color='purple')
        axes[1, 0].set_title('多空组合累计收益率')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 5. 自相关性
        autocorr = self.calculate_autocorrelation()
        lags = [int(k.split('_')[-1]) for k in autocorr.keys()]
        values = list(autocorr.values())
        axes[1, 1].bar(range(len(lags)), values)
        axes[1, 1].set_xticks(range(len(lags)))
        axes[1, 1].set_xticklabels([f'lag_{lag}' for lag in lags])
        axes[1, 1].set_title('因子自相关性')
        axes[1, 1].grid(True, alpha=0.3)
        
        # 6. 分层统计
        quantile_stats = quantile_results['quantile_stats']
        quantile_names = list(quantile_stats.keys())
        mean_returns = [quantile_stats[q]['mean_return'] for q in quantile_names]
        sharpe_ratios = [quantile_stats[q]['sharpe_ratio'] for q in quantile_names]
        
        x = np.arange(len(quantile_names))
        width = 0.35
        axes[1, 2].bar(x - width/2, mean_returns, width, label='平均收益率', alpha=0.8)
        axes[1, 2].bar(x + width/2, sharpe_ratios, width, label='夏普比率', alpha=0.8)
        axes[1, 2].set_xticks(x)
        axes[1, 2].set_xticklabels(quantile_names)
        axes[1, 2].set_title('分层统计')
        axes[1, 2].legend()
        axes[1, 2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        return fig

def preprocess_multiple_factors(
    factors_dict: Dict[str, pd.DataFrame],
    **preprocessing_kwargs
) -> Dict[str, pd.DataFrame]:
    """
    批量预处理多个因子
    :param factors_dict: 因子字典 {因子名: 因子数据}
    :param preprocessing_kwargs: 预处理参数
    :return: 预处理后的因子字典
    """
    preprocessor = FactorPreprocessor()
    processed_factors = {}
    
    for factor_name, factor_data in factors_dict.items():
        processed_data = preprocessor.process_factor(factor_data, **preprocessing_kwargs)
        processed_factors[factor_name] = processed_data
        print(f"✓ 完成因子 {factor_name} 的预处理")
    
    return processed_factors

def check_factor_quality(
    original_factor: pd.DataFrame, 
    processed_factor: pd.DataFrame
) -> Dict:
    """
    检查因子处理质量
    :param original_factor: 原始因子
    :param processed_factor: 处理后因子
    :return: 质量检查结果
    """
    quality_report = {}
    
    # 计算处理前后统计量
    orig_mean = original_factor.mean().mean()
    orig_std = original_factor.std().mean()
    proc_mean = processed_factor.mean().mean()
    proc_std = processed_factor.std().mean()
    
    quality_report['original_mean'] = orig_mean
    quality_report['original_std'] = orig_std
    quality_report['processed_mean'] = proc_mean
    quality_report['processed_std'] = proc_std
    quality_report['mean_change'] = abs(orig_mean - proc_mean)
    quality_report['std_change'] = abs(orig_std - proc_std)
    
    # 检查异常值减少情况
    orig_outliers = ((original_factor > original_factor.mean() + 3 * original_factor.std()) | 
                     (original_factor < original_factor.mean() - 3 * original_factor.std())).sum().sum()
    proc_outliers = ((processed_factor > processed_factor.mean() + 3 * processed_factor.std()) | 
                     (processed_factor < processed_factor.mean() - 3 * processed_factor.std())).sum().sum()
    
    quality_report['original_outliers'] = orig_outliers
    quality_report['processed_outliers'] = proc_outliers
    quality_report['outlier_reduction'] = orig_outliers - proc_outliers
    
    # 计算原始因子和处理后因子的相关性
    correlations = []
    for date in original_factor.index:
        if date in processed_factor.index:
            orig_daily = original_factor.loc[date].dropna()
            proc_daily = processed_factor.loc[date].dropna()
            
            common_stocks = orig_daily.index.intersection(proc_daily.index)
            if len(common_stocks) > 1:
                corr = orig_daily[common_stocks].corr(proc_daily[common_stocks])
                if not np.isnan(corr):
                    correlations.append(corr)
    
    quality_report['preservation_correlation'] = np.mean(correlations) if correlations else 0
    
    return quality_report

def calculate_ic_for_multiple_factors(
    factors_dict: Dict[str, pd.DataFrame], 
    forward_returns: pd.DataFrame
) -> Dict[str, pd.Series]:
    """
    计算多个因子的IC
    :param factors_dict: 因子字典 {因子名: 因子数据}
    :param forward_returns: 未来收益率数据
    :return: 各因子IC序列字典
    """
    ic_results = {}
    
    for factor_name, factor_data in factors_dict.items():
        analyzer = FactorAnalyzer(factor_data, forward_returns)
        ic_results[factor_name] = analyzer.calculate_ic()
    
    return ic_results

def compare_factors_ic(
    factors_dict: Dict[str, pd.DataFrame], 
    forward_returns: pd.DataFrame,
    figsize: Tuple[int, int] = (12, 8)
):
    """
    比较多个因子的IC
    :param factors_dict: 因子字典
    :param forward_returns: 未来收益率数据
    :param figsize: 图表大小
    """
    ic_results = calculate_ic_for_multiple_factors(factors_dict, forward_returns)
    
    plt.figure(figsize=figsize)
    for factor_name, ic_series in ic_results.items():
        plt.plot(ic_series.index, ic_series.values, label=f'{factor_name} IC', alpha=0.7)
    
    plt.title('因子IC比较')
    plt.xlabel('时间')
    plt.ylabel('IC')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    plt.show()

def calculate_factor_contributions(
    factor_returns: Dict[str, pd.Series],
    portfolio_weights: Dict[str, float] = None
) -> Dict:
    """
    计算各因子对组合收益的贡献
    :param factor_returns: 因子收益率字典
    :param portfolio_weights: 组合权重字典
    :return: 因子贡献度字典
    """
    if portfolio_weights is None:
        # 等权
        n_factors = len(factor_returns)
        portfolio_weights = {factor: 1/n_factors for factor in factor_returns.keys()}
    
    # 对齐时间序列
    all_dates = set()
    for ret_series in factor_returns.values():
        all_dates.update(ret_series.index)
    
    aligned_returns = {}
    for factor, ret_series in factor_returns.items():
        aligned_returns[factor] = ret_series.reindex(sorted(list(all_dates))).fillna(0)
    
    # 计算组合收益
    portfolio_return = pd.Series(0, index=sorted(list(all_dates)), dtype=float)
    for factor, weight in portfolio_weights.items():
        portfolio_return += aligned_returns[factor] * weight
    
    # 计算各因子贡献
    contributions = {}
    for factor, weight in portfolio_weights.items():
        contributions[factor] = {
            'weight': weight,
            'avg_return': aligned_returns[factor].mean(),
            'contribution': (aligned_returns[factor] * weight).mean(),
            'volatility': aligned_returns[factor].std()
        }
    
    return {
        'portfolio_return': portfolio_return,
        'factor_contributions': contributions,
        'total_avg_return': portfolio_return.mean(),
        'total_volatility': portfolio_return.std()
    }