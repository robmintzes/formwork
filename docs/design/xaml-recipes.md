# WPF / XAML Component Recipes

Copy-pasteable XAML layouts styled to match our UI design guidelines.

---

## 1. Base Dialog Window Shell

Use this shell as the root template for custom WPF dialog windows.

```xml
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Tool Name" 
        Height="350" Width="400"
        WindowStartupLocation="CenterOwner"
        Background="#F7FAFC"
        FontFamily="Segoe UI, Arial, sans-serif"
        FontSize="12"
        Foreground="#2D3748">
    <Grid Margin="16">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/> <!-- Title Header -->
            <RowDefinition Height="*"/>    <!-- Content Area -->
            <RowDefinition Height="Auto"/> <!-- Footer Actions -->
        </Grid.RowDefinitions>

        <!-- Header -->
        <StackPanel Grid.Row="0" Margin="0,0,0,16">
            <TextBlock FontSize="16" FontWeight="SemiBold" Foreground="#1A365D" Text="Tool Action Header"/>
            <TextBlock FontSize="11" Foreground="#718096" Text="Brief instruction description about what this tool does." TextWrapping="Wrap"/>
        </StackPanel>

        <!-- Content Area -->
        <Border Grid.Row="1" Background="White" BorderBrush="#E2E8F0" BorderThickness="1" CornerRadius="4" Padding="12" Margin="0,0,0,16">
            <Grid>
                <!-- Add inputs / controls here -->
            </Grid>
        </Border>

        <!-- Footer Buttons -->
        <StackPanel Grid.Row="2" Orientation="Horizontal" HorizontalAlignment="Right">
            <Button Content="Cancel" Name="btn_cancel" Width="80" Height="28" Margin="0,0,8,0" Background="#FFFFFF" BorderBrush="#E2E8F0" Foreground="#4A5568"/>
            <Button Content="OK" Name="btn_ok" Width="80" Height="28" Background="#1A365D" Foreground="#FFFFFF" IsDefault="True"/>
        </StackPanel>
    </Grid>
</Window>
```

---

## 2. Standard Form Panel (Label & Input)

Use this grid structure for basic name-and-option select fields inside the content area.

```xml
<Grid>
    <Grid.RowDefinitions>
        <RowDefinition Height="Auto"/>
        <RowDefinition Height="Auto"/>
        <RowDefinition Height="Auto"/>
    </Grid.RowDefinitions>
    
    <!-- Row 1: Text Field Input -->
    <StackPanel Grid.Row="0" Margin="0,0,0,12">
        <Label Content="Enter Parameter Name:" Foreground="#2D3748" Padding="0,0,0,4"/>
        <TextBox Name="txt_param_name" Height="26" VerticalContentAlignment="Center" BorderBrush="#E2E8F0"/>
    </StackPanel>
    
    <!-- Row 2: Dropdown Menu -->
    <StackPanel Grid.Row="1" Margin="0,0,0,12">
        <Label Content="Select Category:" Foreground="#2D3748" Padding="0,0,0,4"/>
        <ComboBox Name="cmb_categories" Height="26" VerticalContentAlignment="Center" BorderBrush="#E2E8F0"/>
    </StackPanel>
    
    <!-- Row 3: Checkbox Option -->
    <CheckBox Grid.Row="2" Content="Apply changes recursively to children elements" Name="chk_recursive" VerticalAlignment="Center" Margin="0,4,0,0"/>
</Grid>
```

---

## 3. Searchable List Selection Box

Use this layout when displaying a list of elements (e.g. sheets, views) with a search filter textbox at the top.

```xml
<Grid>
    <Grid.RowDefinitions>
        <RowDefinition Height="Auto"/> <!-- Search filter textbox -->
        <RowDefinition Height="*"/>    <!-- Scrollable list of items -->
    </Grid.RowDefinitions>

    <!-- Search Text Box -->
    <TextBox Grid.Row="0" Name="txt_search" Height="26" Margin="0,0,0,8" 
             VerticalContentAlignment="Center" BorderBrush="#E2E8F0"/>

    <!-- Scrollable List -->
    <ListBox Grid.Row="1" Name="lst_items" BorderBrush="#E2E8F0" SelectionMode="Multiple">
        <ListBox.ItemTemplate>
            <DataTemplate>
                <StackPanel Orientation="Horizontal" Padding="4">
                    <CheckBox IsChecked="{Binding IsSelected}" Margin="0,0,8,0" VerticalAlignment="Center"/>
                    <TextBlock Text="{Binding DisplayName}" VerticalAlignment="Center"/>
                </StackPanel>
            </DataTemplate>
        </ListBox.ItemTemplate>
    </ListBox>
</Grid>
```
