// Color frames (ImgFrame), object detection (ImgDetections) and age/gender gaze (NNData)
// messages arrive to the host all with some additional delay.
// For each ImgFrame there's one ImgDetections msg, which has multiple detections, and for each
// detection there's a NNData msg which contains age/gender gaze results.//
// How it works:
// Every ImgFrame, ImgDetections and NNData message has it's own sequence number, by which we can sync messages.

#include <map>
#include <memory>
#include <string>
#include <utility>
#include <depthai/depthai.hpp>

class TwoStageHostSeqSync{
    public:
    TwoStageHostSeqSync(){
        msgs.clear();
    }
    // name: color,detection or gaze
    void add_msg(std::shared_ptr<dai::MessageQueue> msg, std::string name){
        int64_t f = -1;
        if(name == "gaze" || name == "landmarks")
            f = msg->get<dai::NNData>()->getSequenceNum();
        else if(name == "color")
            f = msg->get<dai::ImgFrame>()->getSequenceNum();
        else f = msg->get<dai::ImgDetections>()->getSequenceNum();
        auto seq = std::to_string(f); 
        msgs[seq][name].push_back(msg);
    }   

    std::pair<std::map<std::string,std::vector<std::shared_ptr<dai::MessageQueue>>>,int> get_msgs(){
        //std::cout<<"msgs size: "<<msgs.size()<<"\n";
        std::vector<std::string> seq_remove;
        
        for(auto it = msgs.begin(); it != msgs.end();it++){
            auto seq = it->first;
            auto r_msgs = it->second;
            
            seq_remove.push_back(seq); // Will get removed from dict if we find synced msgs pairs
            // Check if we have both detections and color frame with this sequence number
            if(r_msgs.count("color") > 0 && r_msgs.count("detection") > 0){
                // Check if all detected objects (faces) have finished gaze (age/gender) inference
                if(0 < r_msgs["gaze"].size()){
                    // We have synced msgs, remove previous msgs (memory cleaning)
                    for(auto rm : seq_remove){
                        msgs[rm].clear();
                    }
                    return {r_msgs,0}; // Returned synced msgs
                }
            }
        }
        return {msgs["-1"],-1}; // No synced msgs
    }

    private:
        std::map<std::string,std::map<std::string,std::vector<std::shared_ptr<dai::MessageQueue>>>> msgs;
};