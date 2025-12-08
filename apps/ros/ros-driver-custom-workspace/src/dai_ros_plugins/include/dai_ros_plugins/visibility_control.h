#ifndef DAI_ROS_PLUGINS__VISIBILITY_CONTROL_H_
#define DAI_ROS_PLUGINS__VISIBILITY_CONTROL_H_

// This logic was borrowed (then namespaced) from the examples on the gcc wiki:
//     https://gcc.gnu.org/wiki/Visibility

#if defined _WIN32 || defined __CYGWIN__
  #ifdef __GNUC__
    #define DAI_ROS_PLUGINS_EXPORT __attribute__ ((dllexport))
    #define DAI_ROS_PLUGINS_IMPORT __attribute__ ((dllimport))
  #else
    #define DAI_ROS_PLUGINS_EXPORT __declspec(dllexport)
    #define DAI_ROS_PLUGINS_IMPORT __declspec(dllimport)
  #endif
  #ifdef DAI_ROS_PLUGINS_BUILDING_LIBRARY
    #define DAI_ROS_PLUGINS_PUBLIC DAI_ROS_PLUGIN_EXPORT
  #else
    #define DAI_ROS_PLUGINS_PUBLIC DAI_ROS_PLUGIN_IMPORT
  #endif
  #define DAI_ROS_PLUGINS_PUBLIC_TYPE DAI_ROS_PLUGIN_PUBLIC
  #define DAI_ROS_PLUGINS_LOCAL
#else
  #define DAI_ROS_PLUGINS_EXPORT __attribute__ ((visibility("default")))
  #define DAI_ROS_PLUGINS_IMPORT
  #if __GNUC__ >= 4
    #define DAI_ROS_PLUGINS_PUBLIC __attribute__ ((visibility("default")))
    #define DAI_ROS_PLUGINS_LOCAL  __attribute__ ((visibility("hidden")))
  #else
    #define DAI_ROS_PLUGINS_PUBLIC
    #define DAI_ROS_PLUGINS_LOCAL
  #endif
  #define DAI_ROS_PLUGINS_PUBLIC_TYPE
#endif

#endif  // DAI_ROS_PLUGINS__VISIBILITY_CONTROL_H_
